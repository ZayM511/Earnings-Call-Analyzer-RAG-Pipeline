"""Loader for the Rogersurf/earnings-call-transcripts HuggingFace dataset.

This is the primary source for this project because:
1. It contains the Mag 7 companies we care about.
2. It covers the Q2 2024 -> Q1 2026 window with usable density (~39 of the 56
   target calls; gaps documented in the README).
3. It ships as a single parquet, no dataset script, no auth required.

The older `jlh-ibm/earnings_call` dataset only goes through 2020 and uses a
deprecated dataset-script format that the current `datasets` library refuses
to load. We don't use it.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# Canonical Mag 7 tickers. We include both share classes for Alphabet
# (GOOG and GOOGL) because the dataset sometimes labels calls with one and
# sometimes with the other; the chunking layer collapses them to the parent
# company name in `company`.
MAG7_TICKERS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "GOOGL",
    "GOOG",
    "AMZN",
    "META",
    "NVDA",
    "TSLA",
)


# The window we ingest: calls reported between these dates (inclusive).
# Q2 2024 (calls in Apr-Jun 2024) through Q1 2026 (calls in Jan-Mar 2026).
DEFAULT_WINDOW_START = "2024-04-01"
DEFAULT_WINDOW_END = "2026-03-31"


_HF_REPO_ID = "Rogersurf/earnings-call-transcripts"
_HF_FILENAME = "transcripts_clean.parquet"


def load_rogersurf_parquet(cache_dir: str | Path | None = None) -> pd.DataFrame:
    """Download (or load from HF cache) the Rogersurf parquet as a DataFrame.

    Network call only happens on cache miss. Subsequent loads are local-disk.
    """
    # Local import so test modules that don't need the network don't pull in
    # huggingface_hub's transitive imports at collection time.
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        repo_id=_HF_REPO_ID,
        filename=_HF_FILENAME,
        repo_type="dataset",
        cache_dir=str(cache_dir) if cache_dir else None,
    )
    logger.info("loaded Rogersurf parquet from %s", path)
    return pd.read_parquet(path)


def filter_mag7_window(
    df: pd.DataFrame,
    start_date: str = DEFAULT_WINDOW_START,
    end_date: str = DEFAULT_WINDOW_END,
) -> pd.DataFrame:
    """Filter `df` to Mag 7 tickers with `call_date` within [start, end]."""
    dates = pd.to_datetime(df["call_date"], errors="coerce")
    mask = (
        df["ticker"].isin(MAG7_TICKERS)
        & (dates >= pd.Timestamp(start_date))
        & (dates <= pd.Timestamp(end_date))
    )
    out = df.loc[mask].copy()
    # Stable ordering: ticker, then date ascending. Lets downstream code rely
    # on chronological iteration when building multi-quarter trend evals.
    out = out.sort_values(["ticker", "call_date"]).reset_index(drop=True)
    return out


def normalize_quarter(q: int | str) -> str:
    """Convert quarter to canonical 'QN' form. Accepts int (1-4) or 'Q1'/'q1'/'1'."""
    if isinstance(q, int):
        return f"Q{q}"
    s = str(q).strip().upper()
    if s.startswith("Q"):
        return s
    # bare integer-as-string
    if s.isdigit():
        return f"Q{int(s)}"
    raise ValueError(f"Cannot normalize quarter value: {q!r}")
