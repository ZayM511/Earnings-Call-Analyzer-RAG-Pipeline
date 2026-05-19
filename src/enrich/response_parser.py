"""Parse + validate Claude's enrichment response.

Spec'd output is a JSON object with `hedging_score`, `sentiment`, and `topics`.
The parser:
- Tolerates markdown code fences (```json ... ```) and trailing prose.
- Rejects malformed JSON, out-of-range hedging scores, unknown sentiment values,
  non-list topics, and empty topics.
- Lowercases + strips topic strings.
- Truncates topics to 5 entries (extras silently dropped).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_ALLOWED_SENTIMENTS = frozenset({"positive", "neutral", "negative"})
_MAX_TOPICS = 5


class EnrichmentValidationError(ValueError):
    """Raised when Claude's response can't be parsed into a valid enrichment."""


@dataclass(frozen=True)
class EnrichmentResponse:
    hedging_score: float
    sentiment: str
    topics: list[str]


# Match content inside ```json ... ``` or ``` ... ``` code fences.
_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(?P<body>.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


def _extract_json_blob(raw: str) -> str:
    """Strip code fences and trailing prose, return the JSON object substring."""
    text = raw.strip()

    # Strip a markdown code fence if present.
    fence = _CODE_FENCE_RE.search(text)
    if fence:
        text = fence.group("body").strip()

    # If there's prose after the JSON, find the first balanced {...} block.
    if text.startswith("{"):
        depth = 0
        for i, ch in enumerate(text):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[: i + 1]
    # No leading `{` — let json.loads raise downstream.
    return text


def parse_enrichment_response(raw: str) -> EnrichmentResponse:
    """Parse Claude's text response into an `EnrichmentResponse`. Raises on invalid input."""
    if not raw or not raw.strip():
        raise EnrichmentValidationError("empty response")

    blob = _extract_json_blob(raw)
    try:
        obj: Any = json.loads(blob)
    except json.JSONDecodeError as e:
        raise EnrichmentValidationError(f"invalid JSON: {e}") from e

    if not isinstance(obj, dict):
        raise EnrichmentValidationError(f"expected object, got {type(obj).__name__}")

    # hedging_score
    if "hedging_score" not in obj:
        raise EnrichmentValidationError("missing 'hedging_score'")
    raw_hedge = obj["hedging_score"]
    try:
        hedge = float(raw_hedge)
    except (TypeError, ValueError) as e:
        raise EnrichmentValidationError(f"hedging_score not numeric: {raw_hedge!r}") from e
    if not (0.0 <= hedge <= 1.0):
        raise EnrichmentValidationError(f"hedging_score {hedge} out of [0,1]")

    # sentiment
    if "sentiment" not in obj:
        raise EnrichmentValidationError("missing 'sentiment'")
    sentiment = str(obj["sentiment"]).strip().lower()
    if sentiment not in _ALLOWED_SENTIMENTS:
        raise EnrichmentValidationError(
            f"sentiment {sentiment!r} not in {sorted(_ALLOWED_SENTIMENTS)}"
        )

    # topics
    if "topics" not in obj:
        raise EnrichmentValidationError("missing 'topics'")
    raw_topics = obj["topics"]
    if not isinstance(raw_topics, list):
        raise EnrichmentValidationError(f"topics must be a list, got {type(raw_topics).__name__}")
    topics: list[str] = []
    for t in raw_topics:
        s = str(t).strip().lower()
        if s:
            topics.append(s)
    if not topics:
        raise EnrichmentValidationError("topics list is empty after normalization")
    topics = topics[:_MAX_TOPICS]

    return EnrichmentResponse(hedging_score=hedge, sentiment=sentiment, topics=topics)
