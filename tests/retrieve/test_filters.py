"""Tests for src/retrieve/filters.py.

Pure function builds an SQL WHERE fragment + the parameter dict for
psycopg's named-parameter substitution. We assert on shape, not on the
exact SQL string (which would be brittle).
"""

from __future__ import annotations

import re

from src.retrieve.filters import RetrievalFilters, to_sql_where


def test_empty_filters_emit_empty_where_and_no_params() -> None:
    sql, params = to_sql_where(RetrievalFilters())
    assert sql == ""
    assert params == {}


def test_ticker_filter_uses_any_array() -> None:
    sql, params = to_sql_where(RetrievalFilters(tickers=["AAPL", "MSFT"]))
    assert "ticker" in sql.lower()
    assert "any" in sql.lower()
    assert params == {"f_tickers": ["AAPL", "MSFT"]}


def test_year_quarter_filter_uses_separate_columns() -> None:
    sql, params = to_sql_where(RetrievalFilters(year=2024, quarter="Q4"))
    assert "year" in sql
    assert "quarter" in sql
    assert params == {"f_year": 2024, "f_quarter": "Q4"}


def test_section_filter_restricts_to_prepared_or_qa() -> None:
    sql, params = to_sql_where(RetrievalFilters(section="qa"))
    assert "section" in sql
    assert params == {"f_section": "qa"}


def test_speaker_role_filter() -> None:
    sql, params = to_sql_where(RetrievalFilters(speaker_roles=["CEO", "CFO"]))
    assert "speaker_role" in sql
    assert params == {"f_speaker_roles": ["CEO", "CFO"]}


def test_hedging_threshold_filter() -> None:
    sql, params = to_sql_where(RetrievalFilters(min_hedging_score=0.5))
    assert ">=" in sql
    assert params == {"f_min_hedging": 0.5}


def test_topics_filter_uses_array_overlap() -> None:
    sql, params = to_sql_where(RetrievalFilters(topics=["ai capex", "china risk"]))
    # GIN array overlap is && in pgvector / Postgres array semantics.
    assert "&&" in sql
    assert params == {"f_topics": ["ai capex", "china risk"]}


def test_combined_filters_AND_joined() -> None:
    sql, params = to_sql_where(
        RetrievalFilters(
            tickers=["AAPL"],
            year=2024,
            quarter="Q4",
            section="qa",
            speaker_roles=["CEO"],
            min_hedging_score=0.4,
            topics=["ai capex"],
        )
    )
    # All seven clauses must appear and be joined by AND.
    and_count = len(re.findall(r"\bAND\b", sql, flags=re.IGNORECASE))
    assert and_count >= 6
    assert params == {
        "f_tickers": ["AAPL"],
        "f_year": 2024,
        "f_quarter": "Q4",
        "f_section": "qa",
        "f_speaker_roles": ["CEO"],
        "f_min_hedging": 0.4,
        "f_topics": ["ai capex"],
    }


def test_to_sql_where_starts_with_AND_when_not_empty() -> None:
    # Callers compose the fragment after their own WHERE clause; the helper
    # prefixes a leading "AND" so concatenation is safe. Empty filters
    # return empty string.
    sql, _ = to_sql_where(RetrievalFilters(tickers=["AAPL"]))
    assert sql.lstrip().lower().startswith("and ")


def test_filters_dataclass_is_immutable() -> None:
    import dataclasses

    f = RetrievalFilters(tickers=["AAPL"])
    assert dataclasses.is_dataclass(f)
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        f.tickers = []  # type: ignore[misc]
