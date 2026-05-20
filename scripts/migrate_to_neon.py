"""Copy the `chunks` and `ingest_audit` tables from a local Postgres into Neon
(or any other managed Postgres with the pgvector extension).

Usage
-----
    # 1. Make sure `vector` is available on Neon (you can also run this in the
    #    Neon SQL editor): CREATE EXTENSION IF NOT EXISTS vector;
    # 2. Then:
    LOCAL_POSTGRES_URL=postgresql://earningsrag:earningsrag@localhost:5433/earningsrag \
    NEON_POSTGRES_URL=postgresql://user:pass@ep-foo.us-east-1.aws.neon.tech/earningsrag?sslmode=require \
    uv run python -m scripts.migrate_to_neon

What it does
------------
1. Enables the `vector` extension on the destination (no-op if already on).
2. Applies the canonical schema via `src.index.schema.apply_schema`.
3. Streams every row of `chunks` (and `ingest_audit`, if present locally) over
   in 64-row batches, using `executemany` with the pgvector codec registered on
   both ends. The destination's `text_search` column is `GENERATED ALWAYS`, so
   it's not copied — Postgres recomputes it from the inserted `text`.
4. Verifies row counts match before exiting.

Idempotent. Re-running clears the destination's `chunks` first (TRUNCATE) so
the migration always produces a clean replica.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from src.index.schema import apply_schema

logger = logging.getLogger(__name__)

BATCH_SIZE = 64

CHUNK_COLUMNS = (
    "id",
    "text",
    "ticker",
    "company",
    "quarter",
    "year",
    "call_date",
    "speaker_name",
    "speaker_role",
    "section",
    "chunk_index",
    "hedging_score",
    "sentiment",
    "topics",
    "embedding",
    "content_sha256",
    "ingested_at",
)

AUDIT_COLUMNS = (
    "id",
    "source",
    "url",
    "ticker",
    "year",
    "quarter",
    "content_sha256",
    "fetched_at",
)


def _table_exists(conn: psycopg.Connection, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,)
        )
        return cur.fetchone() is not None


def _copy_table(
    src: psycopg.Connection,
    dst: psycopg.Connection,
    table: str,
    columns: tuple[str, ...],
) -> int:
    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    with src.cursor(name=f"copy_{table}") as src_cur:  # server-side cursor
        src_cur.itersize = BATCH_SIZE
        src_cur.execute(f"SELECT {col_list} FROM {table} ORDER BY id")

        batch: list[tuple[Any, ...]] = []
        total = 0
        with dst.cursor() as dst_cur:
            for row in src_cur:
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    dst_cur.executemany(insert_sql, batch)
                    total += len(batch)
                    logger.info("  %s: copied %d so far", table, total)
                    batch = []
            if batch:
                dst_cur.executemany(insert_sql, batch)
                total += len(batch)
        dst.commit()
    return total


def _restart_sequence(dst: psycopg.Connection, table: str) -> None:
    """Re-align the SERIAL sequence to MAX(id) + 1 after explicit-id inserts."""
    with dst.cursor() as cur:
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence(%s, 'id'),"
            f" COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)",
            (table,),
        )
    dst.commit()


def _count(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    local_url = os.environ.get("LOCAL_POSTGRES_URL")
    neon_url = os.environ.get("NEON_POSTGRES_URL")
    if not local_url or not neon_url:
        sys.stderr.write(
            "Both LOCAL_POSTGRES_URL and NEON_POSTGRES_URL env vars must be set.\n"
        )
        return 2

    logger.info("connecting to source: %s", local_url.split("@")[-1])
    logger.info("connecting to destination: %s", neon_url.split("@")[-1])

    # Destination prep: extension + schema.
    with psycopg.connect(neon_url, autocommit=True) as dst_admin, dst_admin.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    logger.info("vector extension ensured on destination")
    apply_schema(neon_url)
    logger.info("schema applied on destination")

    with psycopg.connect(local_url) as src, psycopg.connect(neon_url) as dst:
        register_vector(src)
        register_vector(dst)

        # Wipe destination tables so the script is replayable.
        with dst.cursor() as cur:
            cur.execute("TRUNCATE chunks RESTART IDENTITY")
            if _table_exists(dst, "ingest_audit"):
                cur.execute("TRUNCATE ingest_audit RESTART IDENTITY")
        dst.commit()

        n_chunks = _copy_table(src, dst, "chunks", CHUNK_COLUMNS)
        logger.info("chunks: %d rows copied", n_chunks)

        if _table_exists(src, "ingest_audit"):
            n_audit = _copy_table(src, dst, "ingest_audit", AUDIT_COLUMNS)
            logger.info("ingest_audit: %d rows copied", n_audit)
            _restart_sequence(dst, "ingest_audit")

        _restart_sequence(dst, "chunks")

        src_n = _count(src, "chunks")
        dst_n = _count(dst, "chunks")
        if src_n != dst_n:
            sys.stderr.write(
                f"row count mismatch: source has {src_n}, destination has {dst_n}\n"
            )
            return 3

    logger.info("migration verified: %d chunks copied", src_n)
    print(f"\nDone. {src_n} chunks now live on Neon.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
