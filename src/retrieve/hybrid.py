"""Hybrid retrieval orchestrator.

Pipeline per user question:

  1. Embed the query with voyage-finance-2 (input_type="query").
  2. BM25 search   (top 50 by ts_rank)        in parallel with
     Dense search  (top 50 by 1 - cosine).
     Both honor any RetrievalFilters the caller passes.
  3. Reciprocal Rank Fusion merges the two lists into one ordered
     candidate set (~50-100 unique chunks).
  4. Cohere Rerank 3.5 takes that set + the original question and
     returns the top N (default 10) ordered by cross-encoder relevance.
  5. Returns a list of RetrievedChunk records carrying the chunk's
     full metadata so downstream synthesis can cite cleanly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from src.embed.voyage_rest_client import embed_batch
from src.retrieve.bm25 import BM25Hit, bm25_search
from src.retrieve.dense import DenseHit, dense_search
from src.retrieve.filters import RetrievalFilters
from src.retrieve.rerank import cohere_rerank
from src.retrieve.rrf import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    """Final reranked chunk record passed to synthesis."""

    chunk_id: int
    rerank_score: float       # Cohere's cross-encoder relevance, [0, 1]
    ticker: str
    company: str
    quarter: str
    year: int
    call_date: str
    speaker_name: str | None
    speaker_role: str | None
    section: str | None
    hedging_score: float | None
    sentiment: str | None
    topics: list[str] | None
    text: str


def _hit_to_chunk_dict(hit: BM25Hit | DenseHit) -> dict[str, Any]:
    """Project a BM25 or dense hit into a uniform metadata dict for synthesis."""
    return {
        "chunk_id": hit.chunk_id,
        "ticker": hit.ticker,
        "company": hit.company,
        "quarter": hit.quarter,
        "year": hit.year,
        "call_date": hit.call_date,
        "speaker_name": hit.speaker_name,
        "speaker_role": hit.speaker_role,
        "section": hit.section,
        "hedging_score": hit.hedging_score,
        "sentiment": hit.sentiment,
        "topics": hit.topics,
        "text": hit.text,
    }


def hybrid_retrieve(
    *,
    conn: psycopg.Connection,
    voyage_api_key: str,
    cohere_api_key: str,
    query: str,
    filters: RetrievalFilters | None = None,
    candidate_k: int = 50,
    top_k: int = 10,
    rrf_k: int = 60,
    voyage_model: str = "voyage-finance-2",
) -> list[RetrievedChunk]:
    """Run the full hybrid pipeline and return the top-K reranked chunks."""
    if not query.strip():
        return []

    register_vector(conn)

    # 1. Embed the query.
    [query_vec] = embed_batch(
        [query],
        api_key=voyage_api_key,
        model=voyage_model,
        input_type="query",
    )

    # 2. Two recall lanes.
    bm25_hits = bm25_search(conn, query, filters=filters, limit=candidate_k)
    dense_hits = dense_search(conn, query_vec, filters=filters, limit=candidate_k)

    # 3. RRF merge of the chunk_id rankings.
    bm25_ids = [h.chunk_id for h in bm25_hits]
    dense_ids = [h.chunk_id for h in dense_hits]
    merged = reciprocal_rank_fusion([bm25_ids, dense_ids], k=rrf_k)

    if not merged:
        logger.info("hybrid: 0 candidates after RRF for query %r", query[:80])
        return []

    # Resolve back to metadata. Prefer the BM25 hit if a chunk appears in both
    # lists (text is identical, but holds the BM25 score in `score`). Either
    # works for Cohere; the metadata is the same.
    chunk_table: dict[int, dict[str, Any]] = {}
    for h in dense_hits:
        chunk_table[h.chunk_id] = _hit_to_chunk_dict(h)
    for h in bm25_hits:
        chunk_table[h.chunk_id] = _hit_to_chunk_dict(h)

    merged_chunks = [chunk_table[doc_id] for doc_id, _ in merged if doc_id in chunk_table]
    documents = [str(c["text"]) for c in merged_chunks]

    # 4. Cohere Rerank to top-K.
    rerank_results = cohere_rerank(
        api_key=cohere_api_key,
        query=query,
        documents=documents,
        top_n=top_k,
    )

    # 5. Assemble final list, preserving Cohere's order.
    out: list[RetrievedChunk] = []
    for r in rerank_results:
        c = merged_chunks[r.original_index]
        out.append(
            RetrievedChunk(
                chunk_id=int(c["chunk_id"]),
                rerank_score=r.relevance_score,
                ticker=str(c["ticker"]),
                company=str(c["company"]),
                quarter=str(c["quarter"]),
                year=int(c["year"]),
                call_date=str(c["call_date"]),
                speaker_name=c.get("speaker_name"),
                speaker_role=c.get("speaker_role"),
                section=c.get("section"),
                hedging_score=c.get("hedging_score"),
                sentiment=c.get("sentiment"),
                topics=c.get("topics"),
                text=str(c["text"]),
            )
        )

    logger.info(
        "hybrid: %d BM25 + %d dense -> %d RRF -> %d rerank",
        len(bm25_hits), len(dense_hits), len(merged_chunks), len(out),
    )
    return out
