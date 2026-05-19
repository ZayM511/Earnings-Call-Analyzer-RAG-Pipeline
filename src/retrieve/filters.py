"""Metadata pre-filter builder.

Builds the WHERE-clause fragment + parameter dict that BM25 and dense queries
share. Pre-filtering on metadata is the cheapest accuracy gain in RAG — for
this corpus (~6,300 chunks once the rerank loop runs), a `ticker = 'AAPL'`
filter cuts the candidate set by ~10x before vector search even starts.

Returned SQL fragments are prefixed with `AND` so callers can append:

    cur.execute(f\"\"\"
        SELECT ...
        FROM chunks
        WHERE 1=1
          {sql_fragment}        -- ← inserted here
        ORDER BY ...
    \"\"\", params)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalFilters:
    """Optional metadata pre-filters. Every field defaults to no constraint."""

    tickers: list[str] | None = None
    year: int | None = None
    quarter: str | None = None
    section: str | None = None             # 'prepared' | 'qa'
    speaker_roles: list[str] | None = None  # subset of {CEO, CFO, Analyst, Operator, IR, Other}
    min_hedging_score: float | None = None  # inclusive lower bound on hedging_score
    topics: list[str] | None = None         # array overlap (chunks.topics && filter)


def to_sql_where(filters: RetrievalFilters) -> tuple[str, dict[str, object]]:
    """Return the AND-prefixed WHERE fragment and the named-parameter dict.

    Empty filters return `('', {})`. Otherwise the fragment begins with
    `' AND '` so callers can paste it after their own WHERE clause without
    syntax fussing.
    """
    clauses: list[str] = []
    params: dict[str, object] = {}

    if filters.tickers:
        clauses.append("ticker = ANY(%(f_tickers)s)")
        params["f_tickers"] = list(filters.tickers)

    if filters.year is not None:
        clauses.append("year = %(f_year)s")
        params["f_year"] = int(filters.year)

    if filters.quarter is not None:
        clauses.append("quarter = %(f_quarter)s")
        params["f_quarter"] = str(filters.quarter)

    if filters.section is not None:
        clauses.append("section = %(f_section)s")
        params["f_section"] = str(filters.section)

    if filters.speaker_roles:
        clauses.append("speaker_role = ANY(%(f_speaker_roles)s)")
        params["f_speaker_roles"] = list(filters.speaker_roles)

    if filters.min_hedging_score is not None:
        clauses.append("hedging_score >= %(f_min_hedging)s")
        params["f_min_hedging"] = float(filters.min_hedging_score)

    if filters.topics:
        clauses.append("topics && %(f_topics)s")
        params["f_topics"] = list(filters.topics)

    if not clauses:
        return "", {}

    return " AND " + " AND ".join(clauses), params
