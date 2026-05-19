"""Tests for src/ingest/hf_source.py.

These tests do NOT download the full Rogersurf parquet; they use a small fixture
DataFrame with the same column shape. The download happens in
test_transcript_loaders.py for the one integration test.
"""

from __future__ import annotations

import pandas as pd

from src.ingest.hf_source import (
    MAG7_TICKERS,
    filter_mag7_window,
    normalize_quarter,
)


def _fixture_df() -> pd.DataFrame:
    """Build a small DataFrame with the Rogersurf schema."""
    rows = [
        # In window for Mag 7
        {"ticker": "AAPL", "company": "Apple", "quarter": "Q4", "earnings_year": 2024,
         "call_date": "2024-10-31", "transcript_clean": "x", "transcript": "x",
         "source_url": "https://example/aapl-q4", "title": "Apple Q4 2024"},
        {"ticker": "MSFT", "company": "Microsoft", "quarter": "Q3", "earnings_year": 2024,
         "call_date": "2024-04-25", "transcript_clean": "y", "transcript": "y",
         "source_url": "https://example/msft-q3", "title": "MSFT Q3 2024"},
        # Out of window (too old)
        {"ticker": "AAPL", "company": "Apple", "quarter": "Q1", "earnings_year": 2024,
         "call_date": "2024-02-01", "transcript_clean": "z", "transcript": "z",
         "source_url": "https://example/aapl-q1", "title": "Apple Q1 2024"},
        # Out of window (too new)
        {"ticker": "NVDA", "company": "NVIDIA", "quarter": "Q1", "earnings_year": 2027,
         "call_date": "2026-05-15", "transcript_clean": "w", "transcript": "w",
         "source_url": "https://example/nvda", "title": "NVDA Q1 2027"},
        # Non-Mag-7 ticker — should be filtered out
        {"ticker": "INTC", "company": "Intel", "quarter": "Q2", "earnings_year": 2024,
         "call_date": "2024-07-15", "transcript_clean": "v", "transcript": "v",
         "source_url": "https://example/intc", "title": "INTC Q2 2024"},
        # GOOG (Alphabet alt class) — counted as part of GOOGL
        {"ticker": "GOOG", "company": "Alphabet", "quarter": "Q4", "earnings_year": 2024,
         "call_date": "2025-02-05", "transcript_clean": "u", "transcript": "u",
         "source_url": "https://example/goog", "title": "GOOG Q4 2024"},
    ]
    return pd.DataFrame(rows)


def test_filter_mag7_window_keeps_mag7_in_range() -> None:
    df = _fixture_df()
    out = filter_mag7_window(df, "2024-04-01", "2026-03-31")
    tickers = set(out["ticker"].tolist())
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "GOOG" in tickers  # Alphabet alt class


def test_filter_mag7_window_excludes_out_of_window() -> None:
    df = _fixture_df()
    out = filter_mag7_window(df, "2024-04-01", "2026-03-31")
    dates = set(out["call_date"].astype(str).tolist())
    assert "2024-02-01" not in dates  # Apple Q1 (too old)
    assert "2026-05-15" not in dates  # NVDA Q1 2027 (too new)


def test_filter_mag7_window_excludes_non_mag7() -> None:
    df = _fixture_df()
    out = filter_mag7_window(df, "2024-04-01", "2026-03-31")
    assert "INTC" not in set(out["ticker"].tolist())


def test_mag7_tickers_constant_contains_seven_canonical_tickers() -> None:
    # We accept GOOG as well (Alphabet C-class) so the canonical set is 8.
    expected = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"}
    assert set(MAG7_TICKERS) == expected


def test_normalize_quarter_accepts_int_and_string() -> None:
    assert normalize_quarter(1) == "Q1"
    assert normalize_quarter("Q1") == "Q1"
    assert normalize_quarter("q3") == "Q3"
    assert normalize_quarter(4) == "Q4"
