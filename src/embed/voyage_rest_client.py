"""Voyage AI embeddings via the REST API.

We call the REST endpoint directly instead of going through the `voyageai`
Python SDK because the SDK fails to import on Python 3.14 (a pydantic-v1
+ `min_items` issue inside `voyageai.multimodal_embeddings`). The wire
protocol is the same; only the import path is broken.

API docs: https://docs.voyageai.com/reference/embeddings-api

The two important calibration knobs:
- `model`: `voyage-finance-2` for this project (finance-tuned, 1024 dims).
- `input_type`: `"document"` at ingest, `"query"` at retrieval. Voyage's
  asymmetric encoder loses ~5-10% recall if you mix the two up.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

VOYAGE_ENDPOINT = "https://api.voyageai.com/v1/embeddings"

# Voyage hard caps per call. From the docs.
MAX_BATCH_SIZE = 128
MAX_TOKENS_PER_CALL = 320_000

InputType = Literal["document", "query"]
_ALLOWED_INPUT_TYPES: set[str] = {"document", "query"}


class VoyageError(RuntimeError):
    """Raised on a non-retryable Voyage response (4xx other than 429)."""


# Retry envelope: handle transient 429s, connection blips, and 5xxs.
_RETRYABLE_EXC = (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(_RETRYABLE_EXC),
    reraise=True,
)
def _post_with_retry(payload: dict[str, object], api_key: str, timeout: float) -> httpx.Response:
    response = httpx.post(
        VOYAGE_ENDPOINT,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    # 4xx other than 429 -> non-retryable. 429 + 5xx -> raise so tenacity retries.
    if response.status_code == 429 or response.status_code >= 500:
        response.raise_for_status()
    return response


def embed_batch(
    texts: list[str],
    *,
    api_key: str,
    model: str = "voyage-finance-2",
    input_type: InputType = "document",
    timeout: float = 60.0,
) -> list[list[float]]:
    """Send ONE batch (<=128 texts) and return their embeddings in input order."""
    if not texts:
        raise ValueError("texts must not be empty")
    if len(texts) > MAX_BATCH_SIZE:
        raise ValueError(
            f"batch size {len(texts)} exceeds Voyage's limit of {MAX_BATCH_SIZE}"
        )
    if input_type not in _ALLOWED_INPUT_TYPES:
        raise ValueError(
            f"input_type {input_type!r} must be one of {sorted(_ALLOWED_INPUT_TYPES)}"
        )

    payload: dict[str, object] = {
        "model": model,
        "input": texts,
        "input_type": input_type,
    }

    response = _post_with_retry(payload, api_key=api_key, timeout=timeout)
    if response.status_code != 200:
        # Non-retryable 4xx surfaced here (401, 400, etc.)
        raise VoyageError(
            f"Voyage returned {response.status_code}: {response.text[:300]}"
        )

    body = response.json()
    data = body.get("data") or []
    # Voyage returns items with an `index` field. Sort defensively so callers
    # can rely on order matching the input list.
    data.sort(key=lambda d: d.get("index", 0))
    embeddings = [list(d["embedding"]) for d in data]

    if len(embeddings) != len(texts):
        raise VoyageError(
            f"Voyage returned {len(embeddings)} embeddings for {len(texts)} inputs"
        )
    return embeddings


def embed_texts(
    texts: list[str],
    *,
    api_key: str,
    model: str = "voyage-finance-2",
    input_type: InputType = "document",
    batch_size: int = MAX_BATCH_SIZE,
    timeout: float = 60.0,
) -> list[list[float]]:
    """Embed a list of any size. Splits into batches of `batch_size` automatically."""
    if not texts:
        return []
    if batch_size > MAX_BATCH_SIZE:
        raise ValueError(
            f"batch_size {batch_size} exceeds Voyage's limit of {MAX_BATCH_SIZE}"
        )

    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        out.extend(
            embed_batch(
                batch,
                api_key=api_key,
                model=model,
                input_type=input_type,
                timeout=timeout,
            )
        )
        logger.info(
            "embedded batch %d-%d (size=%d) with %s",
            i,
            i + len(batch),
            len(batch),
            model,
        )
    return out
