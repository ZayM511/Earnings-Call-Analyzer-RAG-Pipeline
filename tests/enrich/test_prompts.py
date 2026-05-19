"""Tests for src/enrich/prompts.py.

The system prompt is cached on the Anthropic side so we want it stable across
calls. The user prompt template is parameterized by chunk metadata.
"""

from __future__ import annotations

import pytest

from src.enrich.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)


def test_system_prompt_is_non_empty_and_mentions_three_fields() -> None:
    assert SYSTEM_PROMPT.strip(), "system prompt is empty"
    # All three extraction fields should be named.
    for field in ("hedging_score", "sentiment", "topics"):
        assert field in SYSTEM_PROMPT


def test_system_prompt_declares_json_only_output() -> None:
    # The downstream parser is strict; the prompt must instruct JSON-only output.
    lowered = SYSTEM_PROMPT.lower()
    assert "json" in lowered


def test_system_prompt_is_stable_for_caching() -> None:
    # Two reads of the same constant must be byte-identical. If a future
    # change introduces a timestamp or random seed into the prompt, caching
    # breaks (every call becomes a cache miss). This test pins the property.
    from src.enrich.prompts import SYSTEM_PROMPT as a
    from src.enrich.prompts import SYSTEM_PROMPT as b

    assert a == b
    assert id(a) == id(b)  # same module-level string object


def test_build_user_prompt_includes_chunk_metadata() -> None:
    prompt = build_user_prompt(
        chunk_text="We delivered record revenue.",
        speaker_name="Tim Cook",
        role="CEO",
        section="prepared",
        company="Apple",
        ticker="AAPL",
        quarter="Q4",
        year=2024,
    )
    for piece in (
        "Tim Cook",
        "CEO",
        "prepared",
        "Apple",
        "AAPL",
        "Q4",
        "2024",
        "We delivered record revenue.",
    ):
        assert piece in prompt, f"missing {piece}"


def test_build_user_prompt_rejects_oversized_chunk_text() -> None:
    huge = "x" * 100_000
    with pytest.raises(ValueError):
        build_user_prompt(
            chunk_text=huge,
            speaker_name="Tim Cook",
            role="CEO",
            section="prepared",
            company="Apple",
            ticker="AAPL",
            quarter="Q4",
            year=2024,
        )
