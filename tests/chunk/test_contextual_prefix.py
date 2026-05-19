"""Tests for src/chunk/contextual_prefix.py.

The contextual-retrieval prefix (Anthropic, 2024) is prepended before
embedding only. The stored `text` column keeps the raw chunk; the prefix is
applied at embed time inside `src/embed/`.
"""

from __future__ import annotations

import pytest

from src.chunk.contextual_prefix import build_prefix, prepend_prefix


def test_build_prefix_uses_all_metadata_fields() -> None:
    prefix = build_prefix(
        company="Apple",
        ticker="AAPL",
        quarter="Q3",
        year=2024,
        speaker_name="Tim Cook",
        role="CEO",
        section="prepared",
    )
    # Each metadata piece appears in the prefix.
    for piece in ("Apple", "Q3", "2024", "Tim Cook", "CEO", "prepared"):
        assert piece in prefix, f"missing {piece}"
    # Prefix ends with a colon so the chunk text appended after reads as a
    # continuation, not as a sentence joined to the prefix's last word.
    assert prefix.rstrip().endswith(":")


def test_build_prefix_handles_qa_section_label() -> None:
    prefix = build_prefix(
        company="Microsoft",
        ticker="MSFT",
        quarter="Q4",
        year=2024,
        speaker_name="Satya Nadella",
        role="CEO",
        section="qa",
    )
    assert "Q&A" in prefix or "qa" in prefix or "Question" in prefix


def test_prepend_prefix_joins_prefix_and_text() -> None:
    out = prepend_prefix(
        chunk_text="Apple Intelligence rollout is going well.",
        company="Apple",
        ticker="AAPL",
        quarter="Q4",
        year=2024,
        speaker_name="Tim Cook",
        role="CEO",
        section="prepared",
    )
    assert "Apple Intelligence rollout is going well." in out
    assert "Apple" in out
    assert "Tim Cook" in out


def test_prepend_prefix_does_not_mutate_chunk_text_field() -> None:
    # The raw chunk should remain unmodified separately; the prefix returns a
    # NEW string. We don't store anything on the chunk object here.
    raw = "Revenue was up."
    out = prepend_prefix(
        chunk_text=raw,
        company="Apple",
        ticker="AAPL",
        quarter="Q3",
        year=2024,
        speaker_name="Tim Cook",
        role="CEO",
        section="prepared",
    )
    assert raw == "Revenue was up."  # unchanged
    assert raw in out and len(out) > len(raw)


def test_prepend_prefix_invalid_section_raises() -> None:
    with pytest.raises(ValueError):
        build_prefix(
            company="Apple",
            ticker="AAPL",
            quarter="Q3",
            year=2024,
            speaker_name="Tim Cook",
            role="CEO",
            section="not_a_section",
        )
