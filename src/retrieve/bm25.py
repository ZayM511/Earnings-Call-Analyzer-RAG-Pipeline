"""BM25 keyword search via Postgres tsvector + ts_rank.

The `text_search` column on `chunks` is a generated tsvector over `text`,
indexed with GIN (see `src/index/schema.py`). `plainto_tsquery` handles
normal English queries safely; for phrase / boolean queries the caller can
switch to `phraseto_tsquery` or `to_tsquery`.

Returns a list of `BM25Hit`s with the chunk's full metadata so downstream
callers (RRF + rerank) don't need a second SELECT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.retrieve.filters import RetrievalFilters, to_sql_where

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BM25Hit:
    chunk_id: int
    score: float
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


def bm25_search(
    conn: psycopg.Connection,
    query: str,
    *,
    filters: RetrievalFilters | None = None,
    limit: int = 50,
) -> list[BM25Hit]:
    """Run a BM25 keyword search against the `chunks` table.

    Empty queries return `[]` (matches Postgres' empty tsquery semantics).
    """
    if not query.strip():
        return []

    filters = filters or RetrievalFilters()
    where_sql, params = to_sql_where(filters)
    params = {**params, "q": query, "lim": int(limit)}

    sql = f"""
        SELECT
            id,
            ts_rank(text_search, plainto_tsquery('english', %(q)s)) AS score,
            ticker, company, quarter, year, call_date,
            speaker_name, speaker_role, section,
            hedging_score, sentiment, topics, text
        FROM chunks
        WHERE text_search @@ plainto_tsquery('english', %(q)s)
          {where_sql}
        ORDER BY score DESC
        LIMIT %(lim)s
    """

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    hits = [_row_to_hit(r) for r in rows]
    logger.info("bm25: %d hits for %r", len(hits), query[:80])
    return hits


def _row_to_hit(row: dict[str, Any]) -> BM25Hit:
    return BM25Hit(
        chunk_id=int(row["id"]),
        score=float(row["score"]),
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
