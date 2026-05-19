"""Light-weight parsing for the raw transcript text dumped by HF datasets.

The HF parquet's `transcript_clean` field still carries a JSON-LD prelude (the
publisher's structured metadata, copy-pasted from the page's `<script
type="application/ld+json">` block). This module trims that prelude so the
chunking phase sees only the actual call text.

Full speaker-turn parsing belongs in `src/chunk/speaker_aware_chunker.py`.
This module's contract stops at "give me the body."
"""

from __future__ import annotations

import re

# Markers that reliably appear at or near the start of an earnings-call body.
# We anchor on the first one we find.
_BODY_MARKERS: tuple[str, ...] = (
    "Prepared Remarks:",
    "Prepared remarks:",
    "Call Participants",
    "Call participants:",
)

# Fallback markers: if no "Prepared Remarks" header, use the first Operator turn.
_OPERATOR_PATTERN = re.compile(r"(?:^|\n)Operator\b", re.MULTILINE)


# If marker-based slicing leaves a body shorter than this, the marker was
# likely a footer reference (e.g., an "Operator" closing line, or a "Call
# Participants" footer block). Return the original text in that case and let
# downstream chunking handle the prelude.
_MIN_SLICED_BODY_LENGTH = 2000


def extract_call_body(text: str) -> str:
    """Return the portion of `text` that looks like the actual transcript body.

    Strategy:
      1. If any of `_BODY_MARKERS` appears and slicing from it leaves >=2000
         chars, use that slice (strips the JSON-LD prelude cleanly).
      2. Otherwise, if there's an `Operator` line in the first half of the
         text and slicing from it leaves >=2000 chars, use that.
      3. Otherwise return the text unchanged (the publisher already stripped
         the prelude, or there's no clean prelude to strip).
    """
    if not text:
        return ""

    earliest = len(text)
    for marker in _BODY_MARKERS:
        idx = text.find(marker)
        if idx != -1 and idx < earliest:
            earliest = idx

    if earliest < len(text):
        body = text[earliest:].strip()
        if len(body) >= _MIN_SLICED_BODY_LENGTH:
            return body
        # Marker was likely a footer; fall through.

    op_match = _OPERATOR_PATTERN.search(text)
    if op_match and op_match.start() < len(text) // 2:
        start = op_match.start()
        if text[start] == "\n":
            start += 1
        body = text[start:].strip()
        if len(body) >= _MIN_SLICED_BODY_LENGTH:
            return body

    return text.strip()


# Crude heuristics for "this body actually contains a transcript."
_MIN_BODY_LENGTH = 500          # chars; anything shorter is likely metadata noise
_LONG_BODY_LENGTH = 2000        # chars; threshold for the "speaker-headers" fallback
_MIN_SPEAKER_HEADERS = 5        # for the Tesla-style "Name: ..." format

# Speaker-header pattern: a line starting with capitalized first-and-last name
# followed by a colon (e.g., "Elon Musk:", "Tim Cook:"). Tesla-style calls use
# this pattern instead of the Operator-led format.
_NAME_COLON_PATTERN = re.compile(r"(?:^|\n)[A-Z][a-z]+ [A-Z][a-zA-Z\.\-]+:", re.MULTILINE)


def is_likely_transcript(body: str) -> bool:
    """Return True if `body` looks like a real earnings-call transcript.

    Accepts three independent shapes:
      1. Body >= 500 chars AND contains at least one `Operator` turn.
      2. Body >= 2000 chars AND contains `Prepared Remarks` (most fool.com calls).
      3. Body >= 2000 chars AND contains at least 5 `Name LastName:` speaker
         headers (Tesla-style calls that skip the operator and dive in).
    """
    if not body or len(body) < _MIN_BODY_LENGTH:
        return False
    if _OPERATOR_PATTERN.search(body):
        return True
    if len(body) >= _LONG_BODY_LENGTH and "Prepared Remarks" in body:
        return True
    if len(body) >= _LONG_BODY_LENGTH and len(_NAME_COLON_PATTERN.findall(body)) >= _MIN_SPEAKER_HEADERS:
        return True
    return False
