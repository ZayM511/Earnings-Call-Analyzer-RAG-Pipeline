"""Dense vector search via pgvector.

We use the cosine-distance operator (`<=>`) since both Voyage and pgvector
default to cosine on the `vector_cosine_ops` opclass attached to
`chunks_embedding_idx`. Mixing operators silently disables index use.

`dense_search` takes a pre-computed query embedding (1024-dim list of
floats). At the higher level, `src/retrieve/hybrid.py` is what calls
`voyage_rest_client.embed_batch([query], input_type="query")` first.
Important: `input_type` must be `"query"` for retrieval — using
`"document"` here costs ~5-10% recall.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from src.retrieve.filters import RetrievalFilters, to_sql_where

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DenseHit:
    chunk_id: int
    similarity: float                     # 1 - cosine distance, higher = better
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


def dense_search(
    conn: psycopg.Connection,
    query_embedding: list[float],
    *,
    filters: RetrievalFilters | None = None,
    limit: int = 50,
    ef_search: int | None = 100,
) -> list[DenseHit]:
    """Run a dense vector search. Caller passes the QUERY embedding (not document)."""
    if not query_embedding:
        raise ValueError("query_embedding must not be empty")

    # Register the pgvector adapter on this connection if it isn't already;
    # idempotent / cheap.
    register_vector(conn)

    filters = filters or RetrievalFilters()
    where_sql, params = to_sql_where(filters)
    params = {**params, "emb": query_embedding, "lim": int(limit)}

    # Raise ef_search at query time for higher recall on the rerank-first
    # stage; default is 40, we want ~100 for the 50-candidate stage.
    if ef_search is not None:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL hnsw.ef_search = {int(ef_search)}")

    sql = f"""
        SELECT
            id,
            1 - (embedding <=> %(emb)s::vector) AS similarity,
            ticker, company, quarter, year, call_date,
            speaker_name, speaker_role, section,
            hedging_score, sentiment, topics, text
        FROM chunks
        WHERE embedding IS NOT NULL
          {where_sql}
        ORDER BY embedding <=> %(emb)s::vector
        LIMIT %(lim)s
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    hits = [_row_to_hit(r) for r in rows]
    logger.info("dense: %d hits", len(hits))
    return hits


def _row_to_hit(row: dict[str, Any]) -> DenseHit:
    return DenseHit(
        chunk_id=int(row["id"]),
        similarity=float(row["similarity"]),
        ticker=str(row["ticker"]),
        company=str(row["company"]),
        quarter=str(row["quarter"]),
        year=int(row["year"]),
        call_date=str(row["call_date"]),
        speaker_name=row.get("speaker_name"),
        speaker_role=row.get("speaker_role"),
        section=row.get("section"),
        hedging_score=row.get("hedging_score"),
        sentiment=row.get("sentiment"),
        topics=list(row["topics"]) if row.get("topics") else None,
        text=str(row["text"]),
    )
