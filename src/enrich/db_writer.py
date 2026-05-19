"""Write enriched chunks to Postgres.

Each chunk row carries the raw text + Phase-5 metadata (speaker, section,
chunk_index) + Phase-6 enrichment (hedging_score, sentiment, topics).
The `embedding` column stays NULL until Phase 7.

Idempotency: ON CONFLICT on the unique index `(ticker, year, quarter,
chunk_index)` performs an UPDATE so re-running the pipeline is safe.
"""

from __future__ import annotations

import logging
from typing import Any

import psycopg

logger = logging.getLogger(__name__)


_UPSERT_SQL = """
INSERT INTO chunks (
    text, ticker, company, quarter, year, call_date,
    speaker_name, speaker_role, section, chunk_index,
    hedging_score, sentiment, topics, content_sha256
)
VALUES (
    %(text)s, %(ticker)s, %(company)s, %(quarter)s, %(year)s, %(call_date)s,
    %(speaker_name)s, %(speaker_role)s, %(section)s, %(chunk_index)s,
    %(hedging_score)s, %(sentiment)s, %(topics)s, %(content_sha256)s
)
ON CONFLICT (ticker, year, quarter, chunk_index) DO UPDATE SET
    text = EXCLUDED.text,
    company = EXCLUDED.company,
    call_date = EXCLUDED.call_date,
    speaker_name = EXCLUDED.speaker_name,
    speaker_role = EXCLUDED.speaker_role,
    section = EXCLUDED.section,
    hedging_score = EXCLUDED.hedging_score,
    sentiment = EXCLUDED.sentiment,
    topics = EXCLUDED.topics,
    content_sha256 = EXCLUDED.content_sha256
RETURNING id
"""


def persist_chunks(
    dsn: str,
    rows: list[dict[str, Any]],
) -> int:
    """Upsert `rows` into the `chunks` table. Returns count of rows touched.

    Each row dict must contain keys: text, ticker, company, quarter, year,
    call_date, speaker_name, speaker_role, section, chunk_index,
    hedging_score, sentiment, topics, content_sha256.
    """
    if not rows:
        return 0
    with psycopg.connect(dsn, autocommit=False) as conn, conn.cursor() as cur:
        for row in rows:
            cur.execute(_UPSERT_SQL, row)
        conn.commit()
    logger.info("upserted %d chunks", len(rows))
    return len(rows)
