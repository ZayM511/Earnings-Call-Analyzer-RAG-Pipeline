"""Phase 6 orchestrator: enrich every chunked transcript via Claude Sonnet 4.5
and persist to Postgres.

Concurrency: bounded by a semaphore. With 8 in-flight calls the 1,097-chunk
corpus takes roughly 6-10 minutes against Anthropic's Tier 4 rate limits.

Resilience:
- Per-call retries with exponential backoff (tenacity, inside `claude_extractor`).
- If a single chunk fails irrecoverably, log and skip; the rest of the call's
  chunks still write.
- DB persistence is idempotent (ON CONFLICT upsert on the unique index).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.chunk.pipeline import load_chunked_jsonl
from src.enrich.claude_extractor import enrich_chunk
from src.enrich.db_writer import persist_chunks
from src.enrich.response_parser import EnrichmentValidationError

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentSummary:
    """Counts captured across one enrichment run."""

    chunks_seen: int = 0
    chunks_enriched: int = 0
    chunks_persisted: int = 0
    chunks_failed: int = 0
    failed_chunks: list[tuple[str, int, str]] = field(default_factory=list)


async def _enrich_one_safe(
    client: Any,
    semaphore: asyncio.Semaphore,
    session_id: str,
    chunk: dict[str, Any],
    summary: EnrichmentSummary,
) -> dict[str, Any] | None:
    """Enrich a single chunk with bounded concurrency. Returns the persisted-shape
    row dict (with `hedging_score`, `sentiment`, `topics` filled in) or `None`
    on failure."""
    async with semaphore:
        try:
            result = await enrich_chunk(
                client=client,
                session_id=session_id,
                chunk=chunk,
            )
        except EnrichmentValidationError as e:
            logger.warning(
                "enrichment validation failed for %s %s %s chunk %d: %s",
                chunk["ticker"], chunk["year"], chunk["quarter"], chunk["chunk_index"], e,
            )
            summary.chunks_failed += 1
            summary.failed_chunks.append(
                (str(chunk["ticker"]), int(chunk["chunk_index"]), str(e))
            )
            return None
        except Exception as e:
            logger.exception(
                "enrichment error for %s %s %s chunk %d",
                chunk["ticker"], chunk["year"], chunk["quarter"], chunk["chunk_index"],
            )
            summary.chunks_failed += 1
            summary.failed_chunks.append(
                (str(chunk["ticker"]), int(chunk["chunk_index"]), repr(e))
            )
            return None

    summary.chunks_enriched += 1
    return {
        "text": chunk["text"],
        "ticker": chunk["ticker"],
        "company": chunk["company"],
        "quarter": chunk["quarter"],
        "year": int(chunk["year"]),
        "call_date": chunk["call_date"],
        "speaker_name": chunk["speaker_name"],
        "speaker_role": chunk["speaker_role"],
        "section": chunk["section"],
        "chunk_index": int(chunk["chunk_index"]),
        "hedging_score": float(result.hedging_score),
        "sentiment": result.sentiment,
        "topics": list(result.topics),
        "content_sha256": chunk.get("content_sha256"),
    }


async def enrich_all(
    *,
    interim_dir: Path | str,
    postgres_dsn: str,
    anthropic_api_key: str,
    concurrency: int = 8,
    session_id: str = "phase6-enrich",
) -> EnrichmentSummary:
    """Run enrichment on every JSONL in `interim_dir` and write to Postgres."""
    # Local import: keeps the unit-test suite (which mocks the client) from
    # paying the anthropic import cost.
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=anthropic_api_key)
    summary = EnrichmentSummary()
    semaphore = asyncio.Semaphore(concurrency)

    interim_dir = Path(interim_dir)
    files = sorted(interim_dir.glob("*_chunks.jsonl"))
    logger.info("enriching %d call files", len(files))

    for path in files:
        chunks: list[dict[str, Any]] = list(load_chunked_jsonl(path))
        if not chunks:
            continue
        summary.chunks_seen += len(chunks)

        # One session per call file so no single session hits the $0.50
        # ceiling. The aggregate hourly circuit breaker still applies.
        per_call_session = f"{session_id}:{path.stem}"

        tasks = [
            _enrich_one_safe(client, semaphore, per_call_session, c, summary)
            for c in chunks
        ]
        results = await asyncio.gather(*tasks)
        rows = [r for r in results if r is not None]

        if rows:
            try:
                persist_chunks(postgres_dsn, rows)
                summary.chunks_persisted += len(rows)
            except Exception as e:
                logger.exception("persist failed for %s: %s", path.name, e)

        logger.info(
            "%s: enriched %d/%d, persisted total=%d",
            path.stem,
            len(rows),
            len(chunks),
            summary.chunks_persisted,
        )

    return summary


def write_summary_jsonl(out_path: Path | str, summary: EnrichmentSummary) -> None:
    """Persist the summary to disk so we have an audit trail per run."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "chunks_seen": summary.chunks_seen,
        "chunks_enriched": summary.chunks_enriched,
        "chunks_persisted": summary.chunks_persisted,
        "chunks_failed": summary.chunks_failed,
        "failed_chunks": [
            {"ticker": t, "chunk_index": i, "error": e} for (t, i, e) in summary.failed_chunks
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
