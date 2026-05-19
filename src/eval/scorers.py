"""Scoring functions for the eval suite.

Each scorer returns a float in [0, 1]. We track:

- retrieval_recall_at_5
    Fraction of the top-5 retrieved chunks whose ticker is in the case's
    expected_tickers set. For single_call / multi_quarter cases this also
    implicitly checks the year+quarter (most of the corpus has many calls
    from many quarters; a 100% ticker match implies the right one was hit).

- retrieval_mrr
    Mean reciprocal rank: 1/k where k is the position of the first chunk
    whose ticker is in expected_tickers. 0 if none.

- theme_coverage
    Fraction of expected_themes (case-insensitive substring match) that
    appear in the synthesized answer.

- citation_count_satisfies_min
    1.0 if parsed citations >= case.expected_min_citations else 0.0.

- llm_judge_answer_quality
    A 0-1 score produced by Claude Opus rating the answer against a rubric.
    Slow + costs ~$0.04/call; reserved for the headline run, not toggled on
    every A/B experiment.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from src.eval.cases import EvalCase
from src.retrieve.hybrid import RetrievedChunk
from src.synthesize.citations import Citation
from src.synthesize.opus_synthesizer import SynthesisResult

logger = logging.getLogger(__name__)


def retrieval_recall_at_5(
    case: EvalCase,
    chunks: list[RetrievedChunk],
) -> float:
    """Fraction of the top-5 retrieved chunks whose ticker is in the expected set."""
    if not case.expected_tickers:
        return 1.0
    top = chunks[:5]
    if not top:
        return 0.0
    expected = set(case.expected_tickers)
    hits = sum(1 for c in top if c.ticker in expected)
    return hits / len(top)


def retrieval_mrr(
    case: EvalCase,
    chunks: list[RetrievedChunk],
) -> float:
    """Reciprocal rank of the first chunk matching expected_tickers."""
    if not case.expected_tickers:
        return 1.0
    expected = set(case.expected_tickers)
    for rank, c in enumerate(chunks, start=1):
        if c.ticker in expected:
            return 1.0 / rank
    return 0.0


def theme_coverage(case: EvalCase, answer: str) -> float:
    """Fraction of expected themes that appear in the answer (case-insensitive)."""
    if not case.expected_themes:
        return 1.0
    lowered = answer.lower()
    hits = sum(1 for theme in case.expected_themes if theme.lower() in lowered)
    return hits / len(case.expected_themes)


def citation_count_satisfies_min(
    case: EvalCase, citations: list[Citation]
) -> float:
    """1.0 if the answer carries at least the expected minimum citations."""
    return 1.0 if len(citations) >= case.expected_min_citations else 0.0


# Per-route grading rubric the LLM judge uses.
JUDGE_RUBRIC = """You are grading an earnings-call RAG answer against the question that produced it.

Rate the answer on three axes, each integer 0-5 (5 = best):

1. groundedness — every factual claim cites a chunk in the format [TICKER QQ YYYY, Speaker]; no invented facts; no outside knowledge bleed.
2. completeness — the answer addresses the literal question asked. For comparison or multi-quarter questions, multiple sources / quarters are referenced.
3. clarity — the answer is well organized; lead with the direct answer; supporting detail second; no padding.

Return ONLY this JSON: {"groundedness": int, "completeness": int, "clarity": int, "rationale": "1-2 sentences"}.
No code fences, no prose before or after."""


async def llm_judge_answer_quality(
    *,
    client: Any,
    case: EvalCase,
    result: SynthesisResult,
) -> tuple[float, dict[str, Any]]:
    """Call Claude Opus to rate the answer 0-5 on three axes; returns
    (overall_score_0_to_1, raw_dict)."""
    user = (
        f"QUESTION: {case.question}\n\n"
        f"EXPECTED THEMES (for grader's reference, not for the answer to follow verbatim): "
        f"{', '.join(case.expected_themes)}\n\n"
        f"ANSWER:\n{result.answer}\n\n"
        f"Now return your JSON judgment."
    )
    response = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        temperature=0.0,
        system=[{"type": "text", "text": JUDGE_RUBRIC, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    parts = [getattr(b, "text", "") for b in response.content if getattr(b, "type", "") == "text"]
    raw_text = "\n".join(parts).strip()
    raw_text = _strip_code_fence(raw_text)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("judge returned non-JSON: %s", raw_text[:200])
        return 0.0, {"raw": raw_text}

    score = (
        int(parsed.get("groundedness", 0))
        + int(parsed.get("completeness", 0))
        + int(parsed.get("clarity", 0))
    ) / 15.0
    return max(0.0, min(1.0, score)), parsed


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL | re.IGNORECASE)


def _strip_code_fence(text: str) -> str:
    m = _CODE_FENCE_RE.search(text)
    return m.group(1).strip() if m else text


# --------------------------------------------------------------------------- #
# Compound per-case score
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CaseScores:
    case_id: str
    recall_at_5: float
    mrr: float
    theme_coverage: float
    citation_min_satisfied: float
    llm_judge: float | None  # None if judge skipped


def score_case(
    case: EvalCase,
    chunks: list[RetrievedChunk],
    answer: str,
    citations: list[Citation],
    llm_judge_score: float | None = None,
) -> CaseScores:
    """Aggregate every scorer for a single case."""
    return CaseScores(
        case_id=case.case_id,
        recall_at_5=retrieval_recall_at_5(case, chunks),
        mrr=retrieval_mrr(case, chunks),
        theme_coverage=theme_coverage(case, answer),
        citation_min_satisfied=citation_count_satisfies_min(case, citations),
        llm_judge=llm_judge_score,
    )
