"""Apply the 200-token floor and 600-token ceiling to a list of `SpeakerTurn`.

Two operations:

1. **Merge small turns** up to a floor. Adjacent short turns (Operator "next
   question", Analyst "thanks for the question") fold into the surrounding
   exec answer. The dominant (longer) turn's `speaker_name`, `role`, and
   `section` win; the absorbed turn's text gets prefixed with
   `"{Role}: {text}\\n\\n"` so chunking preserves the conversational shape.

2. **Split long turns** at sentence boundaries when they exceed the ceiling.
   CFOs occasionally deliver 900-token monologues during prepared remarks;
   splitting at sentence boundaries keeps retrieval precision high without
   shredding semantic units.

`apply_size_bounds` runs both in order: split first (so each piece is bounded
above), then merge (so each piece is bounded below where possible).
"""

from __future__ import annotations

import logging
import re

from src.chunk.speaker_aware_chunker import SpeakerTurn

logger = logging.getLogger(__name__)


# Approximation: 1 token ~= 4 English characters. We're not counting BPE
# tokens here — that would cost too much for 6,000 chunks at ingest time.
# The HF tokenizer drift is small and the 200/600 bounds are advisory.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Cheap token count: chars / 4. Fine at chunking scale."""
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


# Sentence boundary: a `.`, `!`, or `?` followed by whitespace + a capital
# letter (or quote/paren that starts a sentence). Conservative: won't split
# at "U.S." or "Mr. Smith" because the regex requires a following capitalized
# word start after the whitespace.
_SENT_BOUNDARY_RE = re.compile(r"(?<=[\.\!\?])\s+(?=[\"'(]?[A-Z])")


def _split_into_sentences(text: str) -> list[str]:
    parts = _SENT_BOUNDARY_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


# --------------------------------------------------------------------------- #
# split_long_turns
# --------------------------------------------------------------------------- #


def split_long_turns(turns: list[SpeakerTurn], *, ceiling: int = 600) -> list[SpeakerTurn]:
    """Split any turn whose token count exceeds `ceiling` into sub-turns.

    Sub-turns inherit `speaker_name`, `role`, `role_hint`, and `section` from
    the parent. `position` is re-issued across the whole returned list so it
    remains a contiguous index sequence (0..N-1).
    """
    out: list[SpeakerTurn] = []
    next_position = 0
    for turn in turns:
        if estimate_tokens(turn.text) <= ceiling:
            out.append(_repos(turn, next_position))
            next_position += 1
            continue

        sentences = _split_into_sentences(turn.text)
        if len(sentences) <= 1:
            # Can't split at sentence boundaries; emit as-is and log.
            logger.warning(
                "turn from %s at position %d exceeds ceiling but has no "
                "sentence boundaries; emitting unsplit",
                turn.speaker_name,
                turn.position,
            )
            out.append(_repos(turn, next_position))
            next_position += 1
            continue

        current: list[str] = []
        current_tokens = 0
        for sentence in sentences:
            sent_tokens = estimate_tokens(sentence)
            if current and current_tokens + sent_tokens > ceiling:
                # Flush.
                out.append(_repos_with_text(turn, " ".join(current), next_position))
                next_position += 1
                current = []
                current_tokens = 0
            current.append(sentence)
            current_tokens += sent_tokens
        if current:
            out.append(_repos_with_text(turn, " ".join(current), next_position))
            next_position += 1

    return out


def _repos(turn: SpeakerTurn, position: int) -> SpeakerTurn:
    return SpeakerTurn(
        speaker_name=turn.speaker_name,
        role=turn.role,
        role_hint=turn.role_hint,
        text=turn.text,
        section=turn.section,
        position=position,
    )


def _repos_with_text(turn: SpeakerTurn, text: str, position: int) -> SpeakerTurn:
    return SpeakerTurn(
        speaker_name=turn.speaker_name,
        role=turn.role,
        role_hint=turn.role_hint,
        text=text,
        section=turn.section,
        position=position,
    )


# --------------------------------------------------------------------------- #
# merge_small_turns
# --------------------------------------------------------------------------- #


def merge_small_turns(turns: list[SpeakerTurn], *, floor: int = 200) -> list[SpeakerTurn]:
    """Fold tiny turns into adjacent larger ones until each chunk clears `floor`.

    Strategy: walk the list. If a turn is below the floor, attempt to merge
    forward (with the next turn). If forward merge would still leave the result
    too small or there is no next, merge backward. The longer of the two
    turns wins on `speaker_name` / `role` / `section`. The shorter is prefixed
    to the result text as `"{Role}: {text}\\n\\n"`.
    """
    if not turns:
        return []

    result: list[SpeakerTurn] = list(turns)
    i = 0
    while i < len(result):
        turn = result[i]
        if estimate_tokens(turn.text) >= floor:
            i += 1
            continue

        # Decide partner: prefer forward (next turn) unless we're at the end.
        if i + 1 < len(result):
            partner_index = i + 1
        elif i > 0:
            partner_index = i - 1
        else:
            # single-turn list; nothing to merge into
            i += 1
            continue

        merged = _merge_two(turn, result[partner_index])
        # Replace the two source turns with one merged turn.
        lo = min(i, partner_index)
        hi = max(i, partner_index)
        result[lo : hi + 1] = [merged]
        # Restart scanning from the position before the merge so we can keep
        # accumulating if the merged turn is still under the floor.
        i = max(0, lo - 1)

    # Re-number positions to be 0..N-1.
    return [_repos(t, k) for k, t in enumerate(result)]


def _merge_two(a: SpeakerTurn, b: SpeakerTurn) -> SpeakerTurn:
    """Merge two turns. The longer one dominates on metadata.

    Order in the resulting text matches the original order (a came before b
    if `a.position < b.position`; we infer order from the input position).
    """
    if a.position <= b.position:
        first, second = a, b
    else:
        first, second = b, a

    if estimate_tokens(first.text) >= estimate_tokens(second.text):
        dominant = first
    else:
        dominant = second

    # Build merged text. Prefix each non-dominant turn with "{Role}: " so the
    # downstream chunker still sees the conversational handoff.
    parts = []
    for piece in (first, second):
        if piece is dominant:
            parts.append(piece.text)
        else:
            label = piece.role if piece.role != "Other" else piece.speaker_name
            parts.append(f"{label}: {piece.text}")
    merged_text = "\n\n".join(parts)

    return SpeakerTurn(
        speaker_name=dominant.speaker_name,
        role=dominant.role,
        role_hint=dominant.role_hint,
        text=merged_text,
        section=dominant.section,
        position=dominant.position,
    )


# --------------------------------------------------------------------------- #
# Combined pipeline
# --------------------------------------------------------------------------- #


def apply_size_bounds(
    turns: list[SpeakerTurn],
    *,
    floor: int = 200,
    ceiling: int = 600,
) -> list[SpeakerTurn]:
    """Run split-then-merge so output chunks are roughly within [floor, ceiling]."""
    if floor >= ceiling:
        raise ValueError(f"floor ({floor}) must be < ceiling ({ceiling})")
    split = split_long_turns(turns, ceiling=ceiling)
    merged = merge_small_turns(split, floor=floor)
    return merged
