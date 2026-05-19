"""Synthesis: turn retrieved chunks + question into a cited answer.

Uses Claude Opus 4.6 (the most capable model in our cascade) because long-
form synthesis with disciplined citation placement is where the smaller
models start dropping refs or hedging the question. The system prompt is
pinned to ground the answer in the provided chunks; every retrieved chunk
is sanitized via `guardrails.sanitize_retrieved_chunk` before injection so
hostile content (e.g., "ignore previous instructions" planted by an attacker
in a transcript) cannot redirect the model.

Returns a `SynthesisResult` carrying:
  - `answer`: the model's text
  - `citations`: parsed citations in first-appearance order
  - `chunks_used`: a copy of the inputs (for the UI to render alongside)
  - `model`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.guardrails import (
    CostTracker,
    Model,
    estimate_cost,
    guard_request,
    record_usage,
    sanitize_retrieved_chunk,
)
from src.retrieve.hybrid import RetrievedChunk
from src.synthesize.citations import Citation, parse_citations
from src.synthesize.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


# Synthesis model. Long-form answer + careful citation placement -> Opus.
SYNTHESIS_MODEL = Model.OPUS


# Default output budget. Synthesis answers run 3-12 sentences; 1500 tokens
# is comfortable headroom that still fits inside the per-query 2K cap.
_DEFAULT_MAX_OUTPUT_TOKENS = 1500


@dataclass(frozen=True)
class SynthesisResult:
    question: str
    answer: str
    citations: list[Citation]
    chunks_used: list[RetrievedChunk]
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def _sanitize_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Return copies of `chunks` with their text stripped of injection patterns."""
    out: list[RetrievedChunk] = []
    for c in chunks:
        out.append(
            RetrievedChunk(
                chunk_id=c.chunk_id,
                rerank_score=c.rerank_score,
                ticker=c.ticker,
                company=c.company,
                quarter=c.quarter,
                year=c.year,
                call_date=c.call_date,
                speaker_name=c.speaker_name,
                speaker_role=c.speaker_role,
                section=c.section,
                hedging_score=c.hedging_score,
                sentiment=c.sentiment,
                topics=c.topics,
                text=sanitize_retrieved_chunk(c.text),
            )
        )
    return out


def _retryable_types() -> tuple[type[BaseException], ...]:
    try:
        from anthropic import (  # type: ignore[import-untyped]
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            RateLimitError,
        )

        return (RateLimitError, APIConnectionError, APITimeoutError, APIStatusError)
    except Exception:  # pragma: no cover
        return (Exception,)


_RETRY_TYPES = _retryable_types()


async def _call_claude_with_retry(client: Any, kwargs: dict[str, Any]) -> Any:
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(_RETRY_TYPES),
        reraise=True,
    )
    async def _do() -> Any:
        return await client.messages.create(**kwargs)

    return await _do()


async def synthesize(
    *,
    client: Any,
    session_id: str,
    question: str,
    chunks: list[RetrievedChunk],
    tracker: CostTracker | None = None,
    max_output_tokens: int = _DEFAULT_MAX_OUTPUT_TOKENS,
) -> SynthesisResult:
    """Turn `question` + `chunks` into a `SynthesisResult` with inline citations.

    Raises `TokenCapExceeded`, `SessionCostCeilingHit`, `CircuitBreakerOpen`
    if any guardrail fires. The Anthropic SDK's exception types surface if
    retries are exhausted.
    """
    sanitized_chunks = _sanitize_chunks(chunks)
    user_prompt = build_user_prompt(question=question, chunks=sanitized_chunks)

    # Guardrails see the full input (system + user). The system prompt is
    # cached server-side via cache_control, so the bill is mostly user-side
    # after the first call.
    full_input = SYSTEM_PROMPT + "\n" + user_prompt
    input_tokens_est = guard_request(
        session_id=session_id,
        model=SYNTHESIS_MODEL,
        input_text=full_input,
        max_output_tokens=max_output_tokens,
        tracker=tracker,
    )

    kwargs: dict[str, Any] = {
        "model": SYNTHESIS_MODEL.value,
        "max_tokens": max_output_tokens,
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_prompt}],
        # Slightly above zero so the model can pick a fluent phrasing without
        # introducing factual drift on routine questions.
        "temperature": 0.1,
    }

    start = time.perf_counter()
    response = await _call_claude_with_retry(client, kwargs)
    latency_ms = int((time.perf_counter() - start) * 1000)

    usage = getattr(response, "usage", None)
    real_in = int(getattr(usage, "input_tokens", input_tokens_est))
    real_out = int(getattr(usage, "output_tokens", 0))
    record_usage(
        session_id=session_id,
        model=SYNTHESIS_MODEL,
        input_tokens=real_in,
        output_tokens=real_out,
        tracker=tracker,
    )

    # Concatenate any text blocks Claude returned.
    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_parts.append(getattr(block, "text", ""))
    answer = "\n".join(text_parts).strip()

    citations = parse_citations(answer)
    cost = estimate_cost(SYNTHESIS_MODEL, real_in, real_out)

    logger.info(
        "synthesis: session=%s in=%d out=%d cost=$%.4f citations=%d latency=%dms",
        session_id, real_in, real_out, cost, len(citations), latency_ms,
    )

    return SynthesisResult(
        question=question,
        answer=answer,
        citations=citations,
        chunks_used=list(chunks),
        model=SYNTHESIS_MODEL.value,
        input_tokens=real_in,
        output_tokens=real_out,
        cost_usd=cost,
        latency_ms=latency_ms,
    )
