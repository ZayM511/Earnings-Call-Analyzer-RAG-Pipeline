"""Speaker-aware chunking for earnings call transcripts.

This module is the domain primitive of the project. Earnings calls have natural
structure (CEO/CFO prepared remarks, then live Q&A); chunking at speaker
boundaries preserves that structural reality.

Two transcript shapes are supported:

1. **Motley Fool style** (most calls — Apple, MSFT, GOOGL, NVDA, etc.):

       Tim Cook
       --
       Chief Executive Officer

       Thanks for joining...

   Speaker name on its own line, followed by `--`, followed by a role line,
   followed by content.

2. **Tesla style**:

       Elon Musk:
       Thank you. We are at...

   Speaker name followed by `:` on the same line, then content. No role hint;
   the role is inferred from a small `exec_lookup` table.

Both formats may also contain stand-alone `Operator` lines (no `--`, no `:`).
Section flips from `prepared` to `qa` after the Q&A cue (the Operator turn
containing "begin the question-and-answer" or similar, or the IR speaker's
"on to questions" cue in Tesla calls).

Token-bounds work (200-token floor, 600-token ceiling) lives in
`src/chunk/merge_split.py`. This module's contract stops at "give me a list of
SpeakerTurns."
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)


Section = Literal["prepared", "qa"]
Role = Literal["CEO", "CFO", "Analyst", "Operator", "IR", "Other"]


@dataclass(frozen=True)
class SpeakerTurn:
    """One contiguous speaker turn in a transcript."""

    speaker_name: str
    role: str
    role_hint: str | None
    text: str
    section: str
    position: int


# --------------------------------------------------------------------------- #
# Role classification
# --------------------------------------------------------------------------- #

# Patterns we check against the role_hint string, in order of preference.
# First match wins.
_ROLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Order matters: check CFO before CEO so "Senior VP, CFO" doesn't fall
    # through to "Senior VP" or hit something else first. Both check
    # case-insensitively.
    ("CFO", re.compile(r"\b(?:CFO|Chief Financial Officer)\b", re.IGNORECASE)),
    ("CEO", re.compile(r"\b(?:CEO|Chief Executive Officer)\b", re.IGNORECASE)),
    ("Analyst", re.compile(r"\bAnalyst\b", re.IGNORECASE)),
    ("IR", re.compile(r"\bInvestor Relations\b", re.IGNORECASE)),
)


def classify_role(
    role_hint: str | None,
    *,
    speaker_name: str = "",
    exec_lookup: dict[str, str] | None = None,
) -> str:
    """Map a role-hint string (and optionally a speaker name) to a canonical role.

    Returns one of: 'CEO', 'CFO', 'Analyst', 'Operator', 'IR', 'Other'.
    """
    # Operator is identified by speaker name, not role hint.
    if speaker_name.strip().lower() == "operator":
        return "Operator"

    if role_hint:
        for canonical, pattern in _ROLE_PATTERNS:
            if pattern.search(role_hint):
                return canonical

    if exec_lookup and speaker_name in exec_lookup:
        return exec_lookup[speaker_name]

    return "Other"


# --------------------------------------------------------------------------- #
# Format detection
# --------------------------------------------------------------------------- #

# MF header: a speaker name on its own line, followed by `--` on the next line.
# Most calls use this format.
_MF_HEADER_RE = re.compile(
    r"(?:^|\n)([A-Z][A-Za-z][\w\.\-']*(?:\s+[A-Z][\w\.\-']+){1,4})\s*\n--\s*\n([^\n]+)",
)

# Colon header: a speaker name followed by `:` then a newline. Tesla style.
_COLON_HEADER_RE = re.compile(
    r"(?:^|\n)([A-Z][A-Za-z][\w\.\-']*(?:\s+[A-Z][\w\.\-']+){1,4}):\s*\n",
)

# Operator line: just the word "Operator" on its own line. No `--`, no role.
_OPERATOR_LINE_RE = re.compile(r"(?:^|\n)Operator\s*\n", re.MULTILINE)


def detect_format(body: str) -> Literal["mf", "colon"]:
    """Return 'mf' if the body uses Motley-Fool-style headers, else 'colon'.

    Heuristic: count matches of each pattern. The dominant format wins.
    Tie-breaker: 'mf' (most of our corpus).
    """
    mf_count = len(_MF_HEADER_RE.findall(body))
    colon_count = len(_COLON_HEADER_RE.findall(body))
    if colon_count > mf_count:
        return "colon"
    return "mf"


# --------------------------------------------------------------------------- #
# Section transition detection
# --------------------------------------------------------------------------- #

_QA_CUE_RE = re.compile(
    r"(?:"
    r"begin the question[\s\-]?and[\s\-]?answer"
    r"|begin the Q[\s\-]?and[\s\-]?A"
    r"|first question"
    r"|move (?:on )?to questions"
    r"|open the (?:line|floor) (?:for|to) questions"
    r"|now move on to (?:the )?question"
    r"|we'?ll now take questions"
    r"|on to (?:the )?question and answer"
    r")",
    re.IGNORECASE,
)


def _is_qa_cue(text: str) -> bool:
    return bool(_QA_CUE_RE.search(text))


# --------------------------------------------------------------------------- #
# Parser — Motley Fool style
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _RawTurn:
    """Intermediate: a parsed header + its text body, before role classification."""

    speaker_name: str
    role_hint: str | None
    text: str
    start: int  # character offset of the speaker header in the source body


def _parse_mf_raw_turns(body: str) -> list[_RawTurn]:
    """Walk the body and produce raw speaker turns.

    A turn = (speaker header) + (everything between the header's content_start
    and the next header). Operator lines are also treated as headers (they
    have no role hint, content starts on the line after `Operator`).
    """
    # Each header carries: (header_start, name, role_hint_or_None, content_start)
    headers: list[tuple[int, str, str | None, int]] = []

    # MF-style headers: "Name\n--\nRole\n<content>"
    for m in _MF_HEADER_RE.finditer(body):
        name = m.group(1).strip()
        role_hint = m.group(2).strip()
        # m.end() points just past the captured role-hint text. Advance past
        # any trailing newlines/blank lines so content_start is at real content.
        content_start = m.end()
        while content_start < len(body) and body[content_start] in "\n\r":
            content_start += 1
        headers.append((m.start(), name, role_hint, content_start))

    # Operator lines (no `--`, no role hint): "Operator\n<content>"
    for m in _OPERATOR_LINE_RE.finditer(body):
        word_start = m.start() + (1 if body[m.start()] == "\n" else 0)
        # Skip past "Operator\n" and any extra blank lines.
        content_start = m.end()
        while content_start < len(body) and body[content_start] in "\n\r":
            content_start += 1
        headers.append((word_start, "Operator", None, content_start))

    headers.sort(key=lambda x: x[0])

    raw_turns: list[_RawTurn] = []
    for i, (start, name, hint, content_start) in enumerate(headers):
        next_start = headers[i + 1][0] if i + 1 < len(headers) else len(body)
        text = body[content_start:next_start].strip()
        if text:
            raw_turns.append(_RawTurn(speaker_name=name, role_hint=hint, text=text, start=start))
    return raw_turns


def _parse_colon_raw_turns(body: str) -> list[_RawTurn]:
    """Tesla-style: `Name:\\n` followed by content. No role hint."""
    matches = list(_COLON_HEADER_RE.finditer(body))
    raw_turns: list[_RawTurn] = []
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        content_start = m.end()
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        text = body[content_start:next_start].strip()
        if text:
            raw_turns.append(_RawTurn(speaker_name=name, role_hint=None, text=text, start=m.start()))
    return raw_turns


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def parse_speaker_turns(
    body: str,
    *,
    exec_lookup: dict[str, str] | None = None,
) -> list[SpeakerTurn]:
    """Parse `body` into a list of speaker turns.

    Auto-detects MF vs Tesla format. Roles are classified using the role hint
    if present, otherwise via `exec_lookup`. Section flips from `prepared` to
    `qa` on the first Q&A cue.
    """
    if not body:
        return []

    fmt = detect_format(body)
    if fmt == "mf":
        raw_turns = _parse_mf_raw_turns(body)
    else:
        raw_turns = _parse_colon_raw_turns(body)

    section: Section = "prepared"
    turns: list[SpeakerTurn] = []

    # The first analyst-tagged speaker (Tesla style: anyone who isn't a known exec
    # and speaks after the IR cue) marks the start of QA. We track that with a
    # `seen_qa_cue` flag.
    seen_qa_cue = False
    known_execs = set((exec_lookup or {}).keys())

    for idx, raw in enumerate(raw_turns):
        role = classify_role(
            raw.role_hint,
            speaker_name=raw.speaker_name,
            exec_lookup=exec_lookup,
        )

        # For Tesla calls, "Other" speakers who appear after the QA cue are
        # almost always analysts. Promote them.
        if fmt == "colon" and role == "Other" and seen_qa_cue and raw.speaker_name not in known_execs:
            role = "Analyst"

        # Decide if THIS turn flips the section forward.
        # The cue may be inside an Operator turn (MF) or an IR turn (Tesla).
        if not seen_qa_cue and _is_qa_cue(raw.text):
            seen_qa_cue = True
            # The cue-bearing turn itself stays in `prepared` (it's still the
            # operator/IR setting up Q&A). Subsequent turns flip to `qa`.
            assigned_section: Section = "prepared"
        elif seen_qa_cue:
            assigned_section = "qa"
        else:
            assigned_section = "prepared"

        # Heuristic 2: any Analyst-tagged turn (MF style) implies we're in QA.
        if role == "Analyst":
            assigned_section = "qa"
            seen_qa_cue = True

        turns.append(
            SpeakerTurn(
                speaker_name=raw.speaker_name,
                role=role,
                role_hint=raw.role_hint,
                text=raw.text,
                section=assigned_section,
                position=idx,
            )
        )

    return turns
