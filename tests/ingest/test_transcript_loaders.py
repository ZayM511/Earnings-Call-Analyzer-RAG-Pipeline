"""Tests for src/ingest/transcript_loaders.py.

These tests exercise the orchestrator's save logic against a fixture DataFrame.
The real HF download is exercised in a separate `@pytest.mark.integration`
test that we don't run by default.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.ingest.transcript_loaders import (
    output_path_for_call,
    save_transcripts,
)


def _fixture_df() -> pd.DataFrame:
    # Body has to clear the 500-char floor and contain at least one Operator
    # line. We assemble each piece separately so the `* N` applies only to the
    # paragraph we want to repeat (implicit string concatenation runs at lex
    # time and would otherwise multiply everything that came before).
    aapl_prelude = 'Earnings Call Transcript","datePublished":"2024-11-01"...'
    aapl_paragraph = (
        "Tim Cook here with a long opening statement that covers the September "
        "quarter and our outlook on Apple Intelligence. We delivered our best "
        "September quarter ever, with revenue of $94.9 billion, up 6% YoY. "
    )
    aapl_body = (
        "\n\nPrepared Remarks:\n\nOperator\nWelcome to the Apple Q4 call. "
        + (aapl_paragraph * 20)
    )
    aapl_text = aapl_prelude + aapl_body

    msft_paragraph = (
        "Satya Nadella here covering AI capex across Azure, OpenAI infrastructure, "
        "and the broader Microsoft cloud platform. We see continued strong demand. "
    )
    msft_text = (
        "Prepared Remarks:\n\nOperator\nWelcome to the Microsoft fiscal third "
        "quarter call. " + (msft_paragraph * 20)
    )

    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "company": "Apple",
                "quarter": "Q4",
                "earnings_year": 2024,
                "call_date": "2024-10-31",
                "transcript_clean": aapl_text,
                "transcript": "raw text",
                "source_url": "https://example.com/aapl-q4-2024",
                "title": "Apple (AAPL) Q4 2024 Earnings Call Transcript",
            },
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "quarter": "Q3",
                "earnings_year": 2024,
                "call_date": "2024-04-25",
                "transcript_clean": msft_text,
                "transcript": "raw text",
                "source_url": "https://example.com/msft-q3-2024",
                "title": "MSFT Q3 2024",
            },
        ]
    )


def test_output_path_for_call_returns_consistent_name(tmp_path: Path) -> None:
    out = output_path_for_call(tmp_path, ticker="AAPL", year=2024, quarter="Q4")
    assert out.parent == tmp_path
    assert out.name == "AAPL_2024_Q4.json"


def test_save_transcripts_writes_one_json_per_call(tmp_path: Path) -> None:
    df = _fixture_df()
    paths = save_transcripts(df, output_dir=tmp_path)
    assert len(paths) == 2
    assert (tmp_path / "AAPL_2024_Q4.json").exists()
    assert (tmp_path / "MSFT_2024_Q3.json").exists()


def test_save_transcripts_json_contains_expected_keys(tmp_path: Path) -> None:
    df = _fixture_df()
    save_transcripts(df, output_dir=tmp_path)
    obj = json.loads((tmp_path / "AAPL_2024_Q4.json").read_text(encoding="utf-8"))
    for key in ("ticker", "company", "quarter", "year", "date", "full_text", "source_url"):
        assert key in obj, f"missing key {key}"
    assert obj["ticker"] == "AAPL"
    assert obj["year"] == 2024
    assert obj["quarter"] == "Q4"
    # The JSON-LD prelude should be stripped from full_text.
    assert '"datePublished"' not in obj["full_text"]
    # The body should still contain the actual transcript content.
    assert "Apple Intelligence" in obj["full_text"]


def test_save_transcripts_skips_calls_whose_body_is_too_short(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "ticker": "TSLA",
                "company": "Tesla",
                "quarter": "Q1",
                "earnings_year": 2024,
                "call_date": "2024-04-23",
                "transcript_clean": '"datePublished":"x"',  # all metadata, no body
                "transcript": "",
                "source_url": "https://example.com/tsla",
                "title": "Tesla Q1 2024",
            }
        ]
    )
    paths = save_transcripts(df, output_dir=tmp_path)
    assert paths == []
    assert not (tmp_path / "TSLA_2024_Q1.json").exists()


def test_save_transcripts_overwrites_existing(tmp_path: Path) -> None:
    df = _fixture_df()
    save_transcripts(df, output_dir=tmp_path)
    first_size = (tmp_path / "AAPL_2024_Q4.json").stat().st_size
    save_transcripts(df, output_dir=tmp_path)  # idempotent
    second_size = (tmp_path / "AAPL_2024_Q4.json").stat().st_size
    assert first_size == second_size
