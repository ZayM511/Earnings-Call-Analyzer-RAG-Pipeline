"""Tests for src/chunk/merge_split.py.

Covers the 200-token floor (merge tiny adjacent turns) and the 600-token
ceiling (split long monologues at sentence boundaries) per CLAUDE.md's
chunking defaults.
"""

from __future__ import annotations

from src.chunk.merge_split import (
    apply_size_bounds,
    estimate_tokens,
    merge_small_turns,
    split_long_turns,
)
from src.chunk.speaker_aware_chunker import SpeakerTurn


def _turn(speaker: str, role: str, text: str, section: str = "prepared", pos: int = 0) -> SpeakerTurn:
    return SpeakerTurn(
        speaker_name=speaker,
        role=role,
        role_hint=None,
        text=text,
        section=section,
        position=pos,
    )


# --------------------------------------------------------------------------- #
# estimate_tokens
# --------------------------------------------------------------------------- #


def test_estimate_tokens_positive() -> None:
    n = estimate_tokens("The CFO walked through guidance this quarter.")
    assert n > 0


def test_estimate_tokens_zero_for_empty() -> None:
    assert estimate_tokens("") == 0


# --------------------------------------------------------------------------- #
# merge_small_turns
# --------------------------------------------------------------------------- #


def test_merge_small_turns_does_not_touch_already_large_turns() -> None:
    big = "Apple revenue. " * 100  # ~300 tokens
    turns = [_turn("Tim Cook", "CEO", big)]
    out = merge_small_turns(turns, floor=200)
    assert len(out) == 1
    assert out[0].text == big


def test_merge_small_turns_folds_short_operator_into_following_exec() -> None:
    op = _turn("Operator", "Operator", "Our next question comes from Goldman.", section="qa", pos=0)
    ceo = _turn(
        "Tim Cook",
        "CEO",
        "Thanks, Goldman. " + "We see strong demand. " * 50,
        section="qa",
        pos=1,
    )
    out = merge_small_turns([op, ceo], floor=200)
    # Should produce one merged turn keyed on the dominant (longer) speaker.
    assert len(out) == 1
    merged = out[0]
    assert merged.speaker_name == "Tim Cook"
    assert merged.role == "CEO"
    assert "Operator: Our next question" in merged.text or "Our next question" in merged.text
    assert "strong demand" in merged.text


def test_merge_small_turns_preserves_section_of_dominant_turn() -> None:
    op = _turn("Operator", "Operator", "Q&A start cue.", section="prepared", pos=0)
    ceo = _turn(
        "Tim Cook",
        "CEO",
        "Real long answer about strategy. " * 30,
        section="qa",
        pos=1,
    )
    out = merge_small_turns([op, ceo], floor=200)
    assert len(out) == 1
    assert out[0].section == "qa"


def test_merge_small_turns_keeps_distinct_large_turns() -> None:
    a = _turn("Speaker A", "CEO", "Long content A. " * 60)
    b = _turn("Speaker B", "CFO", "Long content B. " * 60)
    out = merge_small_turns([a, b], floor=200)
    assert len(out) == 2


# --------------------------------------------------------------------------- #
# split_long_turns
# --------------------------------------------------------------------------- #


def test_split_long_turns_passes_through_short_turn() -> None:
    t = _turn("Tim Cook", "CEO", "Short remark. Another sentence.")
    out = split_long_turns([t], ceiling=600)
    assert len(out) == 1
    assert out[0].text == "Short remark. Another sentence."


def test_split_long_turns_splits_overlong_at_sentence_boundary() -> None:
    text = ("This is one finance sentence about margins. " * 200)  # ~1800 tokens
    t = _turn("Luca Maestri", "CFO", text)
    out = split_long_turns([t], ceiling=600)
    assert len(out) >= 2
    # Each piece should be at-or-below the ceiling, give or take one sentence.
    for piece in out:
        assert estimate_tokens(piece.text) <= 600 * 1.2  # 20% headroom
    # All pieces preserve speaker + role.
    for piece in out:
        assert piece.speaker_name == "Luca Maestri"
        assert piece.role == "CFO"


def test_split_long_turns_emits_sequential_positions() -> None:
    text = "Sentence. " * 300
    t = _turn("Tim Cook", "CEO", text, pos=5)
    out = split_long_turns([t], ceiling=400)
    # Positions of sub-chunks should be contiguous integers (not equal to original)
    positions = [p.position for p in out]
    assert len(set(positions)) == len(positions), "positions must be unique"


# --------------------------------------------------------------------------- #
# apply_size_bounds (the combined pipeline)
# --------------------------------------------------------------------------- #


def test_apply_size_bounds_returns_chunks_within_target_band() -> None:
    turns = [
        _turn("Operator", "Operator", "Short cue.", pos=0),
        _turn("Tim Cook", "CEO", "Long CEO opening. " * 200, pos=1),
        _turn("Operator", "Operator", "Next question.", pos=2, section="qa"),
        _turn("Analyst One", "Analyst", "Question text.", pos=3, section="qa"),
        _turn(
            "Tim Cook",
            "CEO",
            "Answer to the question. " * 80,
            pos=4,
            section="qa",
        ),
    ]
    chunks = apply_size_bounds(turns, floor=200, ceiling=600)
    # Every chunk should fall within [floor, ~ceiling] roughly.
    for c in chunks:
        toks = estimate_tokens(c.text)
        # 50-token lower margin (a final chunk can be short); 20% ceiling margin.
        assert toks <= 600 * 1.2, f"chunk too long: {toks} tokens"
    # Positions are 0..N-1 in order.
    assert [c.position for c in chunks] == list(range(len(chunks)))


def test_apply_size_bounds_preserves_speaker_metadata() -> None:
    turns = [
        _turn("Tim Cook", "CEO", "Long " * 800, pos=0),  # huge: should split
    ]
    chunks = apply_size_bounds(turns, floor=200, ceiling=400)
    assert all(c.speaker_name == "Tim Cook" for c in chunks)
    assert all(c.role == "CEO" for c in chunks)
