"""Tests for src/enrich/claude_extractor.py.

Mocks the anthropic.AsyncAnthropic client; no live API calls in this file.
Real-API integration goes through tests marked `@pytest.mark.integration`
which we skip by default.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.enrich.claude_extractor import enrich_chunk
from src.enrich.response_parser import EnrichmentValidationError
from src.guardrails import InMemoryCostTracker


def _mock_anthropic_response(json_body: str, *, input_tokens: int = 400, output_tokens: int = 60) -> MagicMock:
    """Build a fake `messages.create()` return value."""
    response = MagicMock()
    response.content = [MagicMock(type="text", text=json_body)]
    response.usage = MagicMock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return response


def _mock_client(json_body: str) -> MagicMock:
    """Build an async-style anthropic client whose messages.create returns a fake response."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_anthropic_response(json_body))
    return client


@pytest.fixture
def tracker() -> InMemoryCostTracker:
    return InMemoryCostTracker()


@pytest.mark.asyncio
async def test_enrich_chunk_happy_path(tracker: InMemoryCostTracker) -> None:
    body = '{"hedging_score": 0.4, "sentiment": "neutral", "topics": ["ai capex"]}'
    client = _mock_client(body)

    out = await enrich_chunk(
        client=client,
        session_id="test-session",
        chunk={
            "text": "Some chunk text.",
            "speaker_name": "Tim Cook",
            "speaker_role": "CEO",
            "section": "qa",
            "company": "Apple",
            "ticker": "AAPL",
            "quarter": "Q3",
            "year": 2024,
        },
        tracker=tracker,
    )

    assert out.hedging_score == 0.4
    assert out.sentiment == "neutral"
    assert out.topics == ["ai capex"]
    # Cost was tracked.
    assert tracker.session_cost("test-session") > 0


@pytest.mark.asyncio
async def test_enrich_chunk_passes_correct_anthropic_kwargs(tracker: InMemoryCostTracker) -> None:
    body = '{"hedging_score": 0.0, "sentiment": "neutral", "topics": ["procedural"]}'
    client = _mock_client(body)

    await enrich_chunk(
        client=client,
        session_id="test-session",
        chunk={
            "text": "Operator: Next question.",
            "speaker_name": "Operator",
            "speaker_role": "Operator",
            "section": "qa",
            "company": "Apple",
            "ticker": "AAPL",
            "quarter": "Q3",
            "year": 2024,
        },
        tracker=tracker,
    )

    # Confirm the call shape: model id, system prompt with cache_control, single user message.
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"].startswith("claude-sonnet-4")
    # System messages should be a list of content blocks with cache_control on the cached one.
    system = kwargs["system"]
    assert isinstance(system, list) and system, "system must be a list of blocks"
    # The first block has the prompt + cache marker.
    first = system[0]
    assert first.get("type") == "text"
    assert "hedging_score" in first.get("text", "")
    assert first.get("cache_control") == {"type": "ephemeral"}
    # User message.
    msgs = kwargs["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


@pytest.mark.asyncio
async def test_enrich_chunk_raises_on_invalid_response(tracker: InMemoryCostTracker) -> None:
    client = _mock_client("not json at all")

    with pytest.raises(EnrichmentValidationError):
        await enrich_chunk(
            client=client,
            session_id="test-session",
            chunk={
                "text": "Some text.",
                "speaker_name": "Tim Cook",
                "speaker_role": "CEO",
                "section": "prepared",
                "company": "Apple",
                "ticker": "AAPL",
                "quarter": "Q3",
                "year": 2024,
            },
            tracker=tracker,
        )


@pytest.mark.asyncio
async def test_enrich_chunk_rejects_oversized_input_before_api_call(tracker: InMemoryCostTracker) -> None:
    """An oversized chunk should be rejected before any API call is made.

    Two layers can catch it: `build_user_prompt`'s char limit (fires first
    for very large inputs) or the guardrails token cap. Both achieve the
    real goal: "no wasted API call."
    """
    huge_text = "x " * 50_000  # well over both limits
    client = _mock_client('{"hedging_score": 0, "sentiment": "neutral", "topics": ["x"]}')

    from src.guardrails import TokenCapExceeded

    with pytest.raises((TokenCapExceeded, ValueError)):
        await enrich_chunk(
            client=client,
            session_id="test-session",
            chunk={
                "text": huge_text,
                "speaker_name": "Tim Cook",
                "speaker_role": "CEO",
                "section": "prepared",
                "company": "Apple",
                "ticker": "AAPL",
                "quarter": "Q3",
                "year": 2024,
            },
            tracker=tracker,
        )

    # No anthropic call should have been made.
    client.messages.create.assert_not_called()
