"""Tests for src/embed/voyage_rest_client.py.

Mocks the Voyage HTTP endpoint with respx so no live API calls happen.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from src.embed.voyage_rest_client import (
    VOYAGE_ENDPOINT,
    VoyageError,
    embed_batch,
    embed_texts,
)


def _mock_response(n: int, dim: int = 1024) -> dict[str, object]:
    """Build a synthetic Voyage embeddings response for `n` items."""
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "embedding": [0.0] * dim,
                "index": i,
            }
            for i in range(n)
        ],
        "model": "voyage-finance-2",
        "usage": {"total_tokens": 1000 * n},
    }


@respx.mock
def test_embed_batch_posts_correct_payload() -> None:
    route = respx.post(VOYAGE_ENDPOINT).mock(
        return_value=httpx.Response(200, json=_mock_response(2))
    )
    out = embed_batch(
        ["chunk one", "chunk two"],
        api_key="test-key",
        model="voyage-finance-2",
        input_type="document",
    )
    assert len(out) == 2
    assert len(out[0]) == 1024

    # Confirm request shape.
    req = route.calls.last.request
    assert req.headers["Authorization"] == "Bearer test-key"
    assert req.headers["Content-Type"] == "application/json"
    import json

    body = json.loads(req.content)
    assert body["model"] == "voyage-finance-2"
    assert body["input"] == ["chunk one", "chunk two"]
    assert body["input_type"] == "document"


@respx.mock
def test_embed_texts_batches_above_128() -> None:
    # 130 texts -> two batches (128 + 2)
    texts = [f"text {i}" for i in range(130)]
    route = respx.post(VOYAGE_ENDPOINT).mock(
        side_effect=[
            httpx.Response(200, json=_mock_response(128)),
            httpx.Response(200, json=_mock_response(2)),
        ]
    )

    out = embed_texts(texts, api_key="test-key", model="voyage-finance-2")
    assert len(out) == 130
    assert route.call_count == 2
    # Each call's batch should be exactly the contract size.
    import json

    sizes = [len(json.loads(c.request.content)["input"]) for c in route.calls]
    assert sizes == [128, 2]


@respx.mock
def test_embed_texts_preserves_order_across_batches() -> None:
    # Each batch returns embeddings with index 0..N-1 in batch-local indexing.
    # The client must concatenate them so the FINAL list matches input order.
    texts = [f"text {i}" for i in range(130)]
    # First batch (128 items): embedding values encode the index as the first dim.
    first_resp = {
        "object": "list",
        "data": [{"embedding": [float(i)] + [0.0] * 1023, "index": i} for i in range(128)],
        "model": "voyage-finance-2",
    }
    second_resp = {
        "object": "list",
        "data": [{"embedding": [float(128 + i)] + [0.0] * 1023, "index": i} for i in range(2)],
        "model": "voyage-finance-2",
    }
    respx.post(VOYAGE_ENDPOINT).mock(
        side_effect=[httpx.Response(200, json=first_resp), httpx.Response(200, json=second_resp)]
    )

    out = embed_texts(texts, api_key="test-key", model="voyage-finance-2")
    # The i-th embedding's first dim must equal i (preserved order).
    for i, vec in enumerate(out):
        assert vec[0] == float(i), f"order broken at index {i}: got {vec[0]}"


@respx.mock
def test_embed_batch_raises_on_4xx() -> None:
    respx.post(VOYAGE_ENDPOINT).mock(
        return_value=httpx.Response(401, json={"detail": "invalid api key"})
    )
    with pytest.raises(VoyageError) as exc_info:
        embed_batch(["x"], api_key="bad", model="voyage-finance-2", input_type="document")
    assert "401" in str(exc_info.value)


@respx.mock
def test_embed_batch_retries_then_succeeds_on_429() -> None:
    respx.post(VOYAGE_ENDPOINT).mock(
        side_effect=[
            httpx.Response(429, json={"detail": "rate limited"}),
            httpx.Response(200, json=_mock_response(1)),
        ]
    )
    out = embed_batch(
        ["one"],
        api_key="test-key",
        model="voyage-finance-2",
        input_type="document",
    )
    assert len(out) == 1


def test_embed_batch_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        embed_batch([], api_key="x", model="voyage-finance-2", input_type="document")


def test_embed_batch_rejects_too_large_batch() -> None:
    # > 128 items per call is a Voyage limit.
    with pytest.raises(ValueError):
        embed_batch(
            ["x"] * 129,
            api_key="x",
            model="voyage-finance-2",
            input_type="document",
        )


def test_embed_batch_rejects_invalid_input_type() -> None:
    with pytest.raises(ValueError):
        embed_batch(
            ["x"],
            api_key="x",
            model="voyage-finance-2",
            input_type="something_else",  # type: ignore[arg-type]
        )
