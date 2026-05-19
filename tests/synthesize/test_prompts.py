"""Tests for src/synthesize/prompts.py."""

from __future__ import annotations

from src.retrieve.hybrid import RetrievedChunk
from src.synthesize.prompts import (
    SYSTEM_PROMPT,
    CITATION_FORMAT_EXAMPLE,
    build_user_prompt,
)


def _chunk(
    chunk_id: int = 1,
    ticker: str = "AAPL",
    quarter: str = "Q4",
    year: int = 2024,
    speaker: str = "Tim Cook",
    role: str = "CEO",
    section: str = "prepared",
    text: str = "We delivered record September quarter revenue.",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        rerank_score=0.9,
        ticker=ticker,
        company="Apple",
        quarter=quarter,
        year=year,
        call_date="2024-10-31",
        speaker_name=speaker,
        speaker_role=role,
        section=section,
        hedging_score=0.2,
        sentiment="positive",
        topics=["revenue growth"],
        text=text,
    )


def test_system_prompt_demands_citations_in_canonical_format() -> None:
    assert "[" in SYSTEM_PROMPT and "]" in SYSTEM_PROMPT
    # The example must literally show the format the parser expects.
    assert CITATION_FORMAT_EXAMPLE in SYSTEM_PROMPT


def test_system_prompt_forbids_answers_without_supporting_chunks() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert "only" in lowered
    # Must include some variant of "if the chunks don't contain an answer".
    assert "don't" in lowered or "do not" in lowered or "cannot" in lowered


def test_build_user_prompt_includes_question_and_every_chunk() -> None:
    chunks = [
        _chunk(chunk_id=1, ticker="AAPL", quarter="Q4", year=2024),
        _chunk(chunk_id=2, ticker="MSFT", quarter="Q3", year=2024, speaker="Satya Nadella", role="CEO"),
    ]
    prompt = build_user_prompt(
        question="How is AI capex trending?",
        chunks=chunks,
    )
    assert "How is AI capex trending?" in prompt
    assert "AAPL Q4 2024" in prompt
    assert "MSFT Q3 2024" in prompt
    assert "Tim Cook" in prompt
    assert "Satya Nadella" in prompt
    # Every chunk's text body should appear.
    assert "September quarter revenue" in prompt


def test_build_user_prompt_assigns_unique_chunk_labels() -> None:
    chunks = [_chunk(chunk_id=10), _chunk(chunk_id=20, ticker="MSFT")]
    prompt = build_user_prompt(question="Q", chunks=chunks)
    # Each chunk should have a labeled header (CHUNK 1 / CHUNK 2 / etc.)
    assert "CHUNK 1" in prompt
    assert "CHUNK 2" in prompt


def test_build_user_prompt_handles_empty_chunks_with_explicit_signal() -> None:
    prompt = build_user_prompt(question="Q", chunks=[])
    # When no chunks come back, the model should be told plainly.
    assert "no chunks" in prompt.lower() or "no relevant" in prompt.lower()
