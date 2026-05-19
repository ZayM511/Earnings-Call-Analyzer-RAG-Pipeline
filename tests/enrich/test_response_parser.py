"""Tests for src/enrich/response_parser.py.

Claude's output is JSON in spec, but in practice models occasionally wrap
the JSON in markdown code fences or trailing prose. The parser tolerates
those failure modes; everything else is rejected.
"""

from __future__ import annotations

import pytest

from src.enrich.response_parser import (
    EnrichmentResponse,
    EnrichmentValidationError,
    parse_enrichment_response,
)


def test_parse_minimal_valid_response() -> None:
    raw = '{"hedging_score": 0.4, "sentiment": "neutral", "topics": ["ai capex"]}'
    out = parse_enrichment_response(raw)
    assert isinstance(out, EnrichmentResponse)
    assert out.hedging_score == 0.4
    assert out.sentiment == "neutral"
    assert out.topics == ["ai capex"]


def test_parse_tolerates_markdown_code_fence() -> None:
    raw = '```json\n{"hedging_score": 0.1, "sentiment": "positive", "topics": ["growth"]}\n```'
    out = parse_enrichment_response(raw)
    assert out.hedging_score == 0.1


def test_parse_tolerates_trailing_prose() -> None:
    raw = (
        '{"hedging_score": 0.2, "sentiment": "positive", "topics": ["q4 guidance"]}'
        "\n\nLet me know if you want me to refine these scores."
    )
    out = parse_enrichment_response(raw)
    assert out.sentiment == "positive"


def test_parse_truncates_topics_above_five() -> None:
    raw = (
        '{"hedging_score": 0.3, "sentiment": "neutral", '
        '"topics": ["one","two","three","four","five","six","seven"]}'
    )
    out = parse_enrichment_response(raw)
    assert len(out.topics) == 5
    assert out.topics == ["one", "two", "three", "four", "five"]


def test_parse_lowercases_and_strips_topics() -> None:
    raw = (
        '{"hedging_score": 0.0, "sentiment": "negative", '
        '"topics": ["  AI Capex  ", "China-Risk"]}'
    )
    out = parse_enrichment_response(raw)
    assert out.topics == ["ai capex", "china-risk"]


def test_parse_rejects_invalid_json() -> None:
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response("not a json object")


def test_parse_rejects_missing_hedging_score() -> None:
    raw = '{"sentiment": "neutral", "topics": ["x"]}'
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response(raw)


def test_parse_rejects_out_of_range_hedging_score() -> None:
    raw = '{"hedging_score": 1.5, "sentiment": "neutral", "topics": ["x"]}'
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response(raw)
    raw = '{"hedging_score": -0.1, "sentiment": "neutral", "topics": ["x"]}'
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response(raw)


def test_parse_rejects_invalid_sentiment() -> None:
    raw = '{"hedging_score": 0.5, "sentiment": "bullish", "topics": ["x"]}'
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response(raw)


def test_parse_rejects_non_list_topics() -> None:
    raw = '{"hedging_score": 0.5, "sentiment": "neutral", "topics": "ai capex"}'
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response(raw)


def test_parse_rejects_empty_topics() -> None:
    raw = '{"hedging_score": 0.5, "sentiment": "neutral", "topics": []}'
    with pytest.raises(EnrichmentValidationError):
        parse_enrichment_response(raw)


def test_parse_coerces_int_hedging_to_float() -> None:
    # 0 and 1 are valid integers; coerce to float.
    raw = '{"hedging_score": 0, "sentiment": "neutral", "topics": ["x"]}'
    out = parse_enrichment_response(raw)
    assert out.hedging_score == 0.0
    assert isinstance(out.hedging_score, float)
