"""Phase 7 orchestrator: embed every chunk in Postgres and UPDATE the
`embedding` column.

The contextual-retrieval prefix from Phase 5 is applied **at embed time
only**. The stored `text` column keeps the raw chunk text so citations
and the UI surface clean quotes; only the vector "knows" the call /
speaker / section context.

Flow:
  1. SELECT id, ticker, company, quarter, year, speaker_name,
     speaker_role, section, text FROM chunks WHERE embedding IS NULL
     ORDER BY id;
  2. For each row, build `prepend_prefix(...)` -> the input text Voyage sees.
  3. Batch 128 inputs -> Voyage `voyage-finance-2` -> 128 vectors.
  4. UPDATE chunks SET embedding = $1 WHERE id = $2 (one statement per
     vector, inside a transaction).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from src.chunk.contextual_prefix import prepend_prefix
from src.embed.voyage_rest_client import (
    MAX_BATCH_SIZE,
    embed_batch,
)

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingSummary:
    rows_seen: int = 0
    rows_embedded: int = 0
    api_calls: int = 0


_SELECT_PENDING_SQL = """
SELECT
    id, ticker, company, quarter, year,
    speaker_name, speaker_role, section, text
FROM chunks
WHERE embedding IS NULL
ORDER BY id
"""

_UPDATE_EMBEDDING_SQL = """
UPDATE chunks SET embedding = %s WHERE id = %s
"""


def _row_to_embed_input(row: dict[str, Any]) -> str:
    """Apply the contextual-retrieval prefix at embed time only."""
    return prepend_prefix(
        chunk_text=str(row["text"]),
        company=str(row["company"]),
        ticker=str(row["ticker"]),
        quarter=str(row["quarter"]),
        year=int(row["year"]),
        speaker_name=str(row["speaker_name"] or "Unknown"),
        role=str(row["speaker_role"] or "Other"),
        section=str(row["section"] or "prepared"),
    )


def embed_pending_chunks(
    *,
    postgres_dsn: str,
    voyage_api_key: str,
    model: str = "voyage-finance-2",
    batch_size: int = MAX_BATCH_SIZE,
) -> EmbeddingSummary:
    """Embed every chunk with NULL embedding. Writes vectors back in-place."""
    summary = EmbeddingSummary()

    with psycopg.connect(postgres_dsn) as conn:
        register_vector(conn)  # pgvector adapter: Python list <-> VECTOR
        # Use server-side cursor by default for the SELECT; with a small
        # corpus this isn't strictly necessary but keeps memory bounded if
        # the corpus grows.
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(_SELECT_PENDING_SQL)
            rows: list[dict[str, Any]] = cur.fetchall()

        summary.rows_seen = len(rows)
        if not rows:
            logger.info("no pending chunks to embed")
            return summary

        # Walk the rows in batches of `batch_size`.
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            inputs = [_row_to_embed_input(r) for r in batch]
            vectors = embed_batch(
                inputs,
                api_key=voyage_api_key,
                model=model,
                input_type="document",
            )
            summary.api_calls += 1

            # Write the batch's vectors back in one transaction.
            with conn.cursor() as cur:
                for row, vec in zip(batch, vectors, strict=True):
                    cur.execute(_UPDATE_EMBEDDING_SQL, (vec, row["id"]))
                conn.commit()

            summary.rows_embedded += len(batch)
            logger.info(
                "embedded batch %d-%d (size=%d), total=%d/%d",
                offset,
                offset + len(batch),
                len(batch),
                summary.rows_embedded,
                summary.rows_seen,
            )

    return summary
