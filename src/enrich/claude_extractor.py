"""Async Claude Sonnet 4.5 enrichment.

`enrich_chunk` runs every chunk through the guardrails wrapper (LLM10
caps + cost tracker), calls Anthropic with the prompt-caching marker on
the system message, parses the response, and returns an
`EnrichmentResponse`.

Concurrency is the caller's responsibility — see `src/enrich/pipeline.py`
for the asyncio.gather + semaphore wrapper used at the 1,097-chunk scale.
"""

from __future__ import annotations

import logging
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.enrich.prompts import SYSTEM_PROMPT, build_user_prompt
from src.enrich.response_parser import EnrichmentResponse, parse_enrichment_response
from src.guardrails import (
    CostTracker,
    Model,
    guard_request,
    record_usage,
)

logger = logging.getLogger(__name__)


# The enrichment model. Sonnet 4.5 is the right balance of calibration and cost
# for hedging-score extraction; Haiku undercounts hedging on subtle phrases.
ENRICHMENT_MODEL = Model.SONNET


# Output budget. Enrichment responses are tiny (~50 tokens for the JSON object).
_MAX_OUTPUT_TOKENS = 256


def _build_anthropic_kwargs(*, user_prompt: str) -> dict[str, Any]:
    """Build the kwargs dict for `client.messages.create(...)`.

    The system prompt is wrapped in a single block with `cache_control:
    {"type": "ephemeral"}` so Anthropic's prompt cache amortizes its tokens
    across calls. The user prompt is per-call and never cached.
    """
    return {
        "model": ENRICHMENT_MODEL.value,
        "max_tokens": _MAX_OUTPUT_TOKENS,
        # System as a list of content blocks lets us attach cache_control.
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [
            {
                "role": "user",
                "content": user_prompt,
            }
        ],
        # Lower temperature -> more deterministic scoring; helps eval stability.
        "temperature": 0.0,
    }


# Anthropic SDK exception types we want to retry on. Imported lazily so the
# import path stays cheap when running unit tests against a mock client.
def _retryable_exception_types() -> tuple[type[BaseException], ...]:
    types: list[type[BaseException]] = []
    try:
        from anthropic import (  # type: ignore[import-untyped]
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            RateLimitError,
        )

        types.extend([RateLimitError, APIConnectionError, APITimeoutError, APIStatusError])
    except Exception:  # pragma: no cover -- defensive
        pass
    return tuple(types)


_RETRY_TYPES = _retryable_exception_types() or (Exception,)


async def _call_claude_with_retry(client: Any, kwargs: dict[str, Any]) -> Any:
    """Issue the messages.create call with exponential backoff on transient errors."""

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(_RETRY_TYPES),
        reraise=True,
    )
    async def _do() -> Any:
        return await client.messages.create(**kwargs)

    return await _do()


async def enrich_chunk(
    *,
    client: Any,
    session_id: str,
    chunk: dict[str, Any],
    tracker: CostTracker | None = None,
) -> EnrichmentResponse:
    """Extract hedging_score, sentiment, and topics for a single chunk.

    Raises `TokenCapExceeded` if the input prompt would breach the per-query
    cap, `EnrichmentValidationError` if Claude's response can't be parsed,
    and the underlying Anthropic exception types if the call still fails
    after retries.
    """
    user_prompt = build_user_prompt(
        chunk_text=str(chunk["text"]),
        speaker_name=str(chunk["speaker_name"]),
        role=str(chunk["speaker_role"]),
        section=str(chunk["section"]),
        company=str(chunk["company"]),
        ticker=str(chunk["ticker"]),
        quarter=str(chunk["quarter"]),
        year=int(chunk["year"]),
    )

    # The guarded_call context manager runs the cap check on the FULL input
    # (system + user). We approximate the system size on top of the user
    # prompt; tiktoken inside count_tokens handles either.
    full_input = SYSTEM_PROMPT + "\n" + user_prompt
    input_tokens = guard_request(
        session_id=session_id,
        model=ENRICHMENT_MODEL,
        input_text=full_input,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        tracker=tracker,
    )

    kwargs = _build_anthropic_kwargs(user_prompt=user_prompt)
    response = await _call_claude_with_retry(client, kwargs)

    # Record actual usage from the response.
    usage = getattr(response, "usage", None)
    real_in = int(getattr(usage, "input_tokens", input_tokens))
    real_out = int(getattr(usage, "output_tokens", 0))
    record_usage(
        session_id=session_id,
        model=ENRICHMENT_MODEL,
        input_tokens=real_in,
        output_tokens=real_out,
        tracker=tracker,
    )

    # Concatenate all text blocks in the response (Claude returns a list).
    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", "") == "text":
            text_parts.append(getattr(block, "text", ""))
    raw_text = "\n".join(text_parts)

    return parse_enrichment_response(raw_text)
