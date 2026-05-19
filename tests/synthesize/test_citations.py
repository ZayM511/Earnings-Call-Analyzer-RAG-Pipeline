"""Tests for src/synthesize/citations.py.

Parses inline citations like `[AAPL Q4 2024, Tim Cook]` out of the model's
answer and returns a structured list. Robust to surrounding punctuation.
"""

from __future__ import annotations

from src.synthesize.citations import Citation, parse_citations


def test_parse_single_citation() -> None:
    text = "Apple grew Services revenue [AAPL Q4 2024, Tim Cook]."
    out = parse_citations(text)
    assert out == [Citation(ticker="AAPL", quarter="Q4", year=2024, speaker="Tim Cook")]


def test_parse_multiple_citations() -> None:
    text = (
        "AI capex stepped up in 2024 [MSFT Q3 2024, Satya Nadella] and continued "
        "into 2025 [MSFT Q1 2025, Amy Hood]."
    )
    out = parse_citations(text)
    assert len(out) == 2
    assert out[0].ticker == "MSFT"
    assert out[0].speaker == "Satya Nadella"
    assert out[1].speaker == "Amy Hood"


def test_parse_handles_compound_quarter_year_formats() -> None:
    # The canonical format is "QQ YYYY" inside the brackets.
    text = "Per CFO commentary [AAPL Q3 2024, Luca Maestri]."
    out = parse_citations(text)
    assert out[0].quarter == "Q3"
    assert out[0].year == 2024


def test_parse_handles_speaker_names_with_punctuation() -> None:
    # "Colette M. Kress" has periods; "Karl-Anthony Towns" has a hyphen.
    text = (
        "Data-center revenue accelerated [NVDA Q2 2025, Colette M. Kress] "
        "and gross margin compressed [NVDA Q2 2025, Jen-Hsun Huang]."
    )
    out = parse_citations(text)
    speakers = [c.speaker for c in out]
    assert "Colette M. Kress" in speakers
    assert "Jen-Hsun Huang" in speakers


def test_parse_ignores_brackets_that_are_not_citations() -> None:
    text = "We expect a 10% lift [eval pending] in retrieval recall."
    assert parse_citations(text) == []


def test_parse_returns_empty_for_text_without_citations() -> None:
    assert parse_citations("Plain answer with no citations.") == []


def test_parse_dedupes_identical_citations() -> None:
    text = (
        "Apple Intelligence [AAPL Q4 2024, Tim Cook] is rolling out, and "
        "the iPhone narrative changed [AAPL Q4 2024, Tim Cook]."
    )
    out = parse_citations(text)
    assert len(out) == 1


def test_parse_preserves_order_of_first_occurrence() -> None:
    text = (
        "MSFT first [MSFT Q3 2024, Satya Nadella] then "
        "AAPL [AAPL Q4 2024, Tim Cook] then back to MSFT "
        "[MSFT Q3 2024, Satya Nadella]."
    )
    out = parse_citations(text)
    assert [c.ticker for c in out] == ["MSFT", "AAPL"]
