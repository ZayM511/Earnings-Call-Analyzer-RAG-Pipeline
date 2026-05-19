"""End-to-end ask: hybrid retrieve + synthesize.

Single async function so callers (CLI, API server, eval runner) all reuse
the same path.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import psycopg

from src.retrieve.filters import RetrievalFilters
from src.retrieve.hybrid import RetrievedChunk, hybrid_retrieve
from src.synthesize.opus_synthesizer import SynthesisResult, synthesize

logger = logging.getLogger(__name__)


async def ask(
    *,
    question: str,
    conn: psycopg.Connection,
    anthropic_client: Any,
    voyage_api_key: str,
    cohere_api_key: str,
    filters: RetrievalFilters | None = None,
    candidate_k: int = 50,
    top_k: int = 10,
    session_id: str | None = None,
) -> SynthesisResult:
    """Retrieve top-K chunks and synthesize a cited answer."""
    session_id = session_id or f"ask:{uuid.uuid4().hex[:8]}"

    chunks: list[RetrievedChunk] = hybrid_retrieve(
        conn=conn,
        voyage_api_key=voyage_api_key,
        cohere_api_key=cohere_api_key,
        query=question,
        filters=filters,
        candidate_k=candidate_k,
        top_k=top_k,
    )

    return await synthesize(
        client=anthropic_client,
        session_id=session_id,
        question=question,
        chunks=chunks,
    )
