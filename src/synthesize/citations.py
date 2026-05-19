"""Parse inline citations of the form `[TICKER QQ YYYY, Speaker Name]`.

The synthesizer's system prompt locks the model into this exact format.
The parser extracts citations in first-appearance order with duplicates
removed, so downstream UIs (citation chips, source list) can render them
without further normalization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Captures: [TICKER QQ YYYY, Speaker Name]
# - TICKER: 1-5 uppercase letters (covers all Mag 7: AAPL, MSFT, GOOG, GOOGL,
#   AMZN, META, NVDA, TSLA, plus any future extensions).
# - QUARTER: literal Q followed by 1-4.
# - YEAR: 4 digits.
# - Speaker Name: anything up to the closing bracket that isn't a bracket.
_CITATION_RE = re.compile(
    r"\["
    r"(?P<ticker>[A-Z]{1,5})\s+"
    r"(?P<quarter>Q[1-4])\s+"
    r"(?P<year>\d{4})"
    r"\s*,\s*"
    r"(?P<speaker>[^\]\[]+?)"
    r"\s*\]"
)


@dataclass(frozen=True)
class Citation:
    ticker: str
    quarter: str
    year: int
    speaker: str


def parse_citations(text: str) -> list[Citation]:
    """Return the unique citations in `text` in first-appearance order."""
    seen: set[tuple[str, str, int, str]] = set()
    out: list[Citation] = []
    for m in _CITATION_RE.finditer(text):
        cit = Citation(
            ticker=m.group("ticker"),
            quarter=m.group("quarter"),
            year=int(m.group("year")),
            speaker=m.group("speaker").strip(),
        )
        key = (cit.ticker, cit.quarter, cit.year, cit.speaker)
        if key in seen:
            continue
        seen.add(key)
        out.append(cit)
    return out
