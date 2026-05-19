"""Audit log for transcript ingestion (OWASP LLM04 — data poisoning defense).

Every transcript that lands on disk gets a row in `ingest_audit` with:
  - source (the HF dataset id, the URL, etc.)
  - the source URL we pulled the text from
  - ticker / year / quarter
  - content_sha256 of the body that was saved
  - fetched_at timestamp

Operators can later check that the corpus only contains content from the
configured allowlist of sources, and detect tampering by hashing the on-disk
file and comparing to the row.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import psycopg

logger = logging.getLogger(__name__)


def insert_audit_rows(
    dsn: str,
    *,
    json_paths: list[Path],
    source_label: str = "huggingface:Rogersurf/earnings-call-transcripts",
) -> int:
    """Write one row to `ingest_audit` per saved transcript JSON.

    Returns the number of rows inserted.
    """
    rows_inserted = 0
    with psycopg.connect(dsn, autocommit=False) as conn, conn.cursor() as cur:
        for path in json_paths:
            obj = json.loads(path.read_text(encoding="utf-8"))
            body = str(obj.get("full_text", ""))
            sha = hashlib.sha256(body.encode("utf-8", errors="replace")).hexdigest()
            cur.execute(
                """
                INSERT INTO ingest_audit
                    (source, url, ticker, year, quarter, content_sha256)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    source_label,
                    str(obj.get("source_url", "")),
                    str(obj.get("ticker", "")),
                    int(obj.get("year", 0)),
                    str(obj.get("quarter", "")),
                    sha,
                ),
            )
            rows_inserted += 1
        conn.commit()
    logger.info("inserted %d audit rows from %s", rows_inserted, source_label)
    return rows_inserted
