"""Cohere Rerank 3.5 wrapper.

Two-stage retrieval is the standard pattern in 2026: cheap recall stage
(BM25 + dense) casts a wide net (~50-100 candidates), then a slow precision
stage (cross-encoder reranker) re-orders the top.

Cohere's `rerank-v3.5` is the right balance of latency + accuracy for the
final stage. We send the user question + the candidate texts; Cohere
returns each candidate with a relevance score in [0, 1] and the SDK
preserves the original index so we can map back to the chunk metadata.

Free tier: 1000 calls / month. At 30 eval queries plus light testing, we
use ~5% of the cap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


_RERANK_MODEL = "rerank-v3.5"


@dataclass(frozen=True)
class RerankResult:
    """A single reranked candidate, keyed back to the input index."""

    original_index: int
    relevance_score: float


def _retryable_types() -> tuple[type[BaseException], ...]:
    """Cohere SDK exceptions we want to retry on (rate limit + 5xx + timeouts)."""
    try:
        from cohere.errors import (  # type: ignore[import-not-found]
            BadRequestError,
            InternalServerError,
            ServiceUnavailableError,
            TooManyRequestsError,
        )

        # We retry TooManyRequests + 5xx; BadRequestError is non-retryable.
        del BadRequestError  # imported for the type-existence side effect
        return (TooManyRequestsError, InternalServerError, ServiceUnavailableError)
    except Exception:  # pragma: no cover -- defensive
        return (Exception,)


_RETRY_TYPES = _retryable_types()


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(_RETRY_TYPES),
    reraise=True,
)
def _rerank_with_retry(client: Any, **kwargs: Any) -> Any:
    return client.rerank(**kwargs)


def cohere_rerank(
    *,
    api_key: str,
    query: str,
    documents: list[str],
    top_n: int = 10,
    model: str = _RERANK_MODEL,
) -> list[RerankResult]:
    """Rerank `documents` against `query`. Returns the top-N by relevance.

    Each result carries `original_index` (into `documents`) so callers
    can pull the matching chunk metadata back out without sending it
    over the wire.
    """
    if not documents:
        return []
    if top_n < 1:
        raise ValueError(f"top_n must be >= 1, got {top_n}")

    # Local import — keeps unit-test suites that mock cohere from paying
    # the import cost.
    import cohere

    client = cohere.ClientV2(api_key=api_key)
    response = _rerank_with_retry(
        client,
        model=model,
        query=query,
        documents=documents,
        top_n=min(top_n, len(documents)),
    )

    results: list[RerankResult] = []
    for r in response.results:
        results.append(
            RerankResult(
                original_index=int(r.index),
                relevance_score=float(r.relevance_score),
            )
        )
    logger.info("cohere rerank: returned %d / %d candidates", len(results), len(documents))
    return results
