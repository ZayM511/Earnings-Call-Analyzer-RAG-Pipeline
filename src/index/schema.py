"""Database schema migration.

Idempotently creates the `chunks` table and its indexes against the configured
`POSTGRES_URL`. Run once after `docker compose up -d`:

    uv run python -m src.index.schema

The pgvector and pg_trgm extensions are enabled by `docker/initdb/01_extensions.sql`
on the container's first startup, so this script does not re-enable them.
"""

from __future__ import annotations

import logging
import sys

import psycopg

from src.config import get_settings

logger = logging.getLogger(__name__)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    id              SERIAL PRIMARY KEY,
    text            TEXT NOT NULL,
    ticker          VARCHAR(10) NOT NULL,
    company         VARCHAR(100) NOT NULL,
    quarter         VARCHAR(4)  NOT NULL,
    year            INT         NOT NULL,
    call_date       DATE        NOT NULL,
    speaker_name    TEXT,
    speaker_role    VARCHAR(20),
    section         VARCHAR(20),
    chunk_index     INT,
    hedging_score   REAL,
    sentiment       VARCHAR(20),
    topics          TEXT[],
    text_search     tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding       VECTOR(1024),
    content_sha256  CHAR(64),
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS chunks_search_idx
    ON chunks USING GIN (text_search);

CREATE INDEX IF NOT EXISTS chunks_ticker_idx
    ON chunks (ticker);

CREATE INDEX IF NOT EXISTS chunks_year_quarter_idx
    ON chunks (year, quarter);

CREATE INDEX IF NOT EXISTS chunks_speaker_role_idx
    ON chunks (speaker_role);

CREATE INDEX IF NOT EXISTS chunks_topics_gin_idx
    ON chunks USING GIN (topics);

CREATE UNIQUE INDEX IF NOT EXISTS chunks_unique_per_call_idx
    ON chunks (ticker, year, quarter, chunk_index);

CREATE TABLE IF NOT EXISTS ingest_audit (
    id            SERIAL PRIMARY KEY,
    source        VARCHAR(120) NOT NULL,
    url           TEXT,
    ticker        VARCHAR(10),
    year          INT,
    quarter       VARCHAR(4),
    content_sha256 CHAR(64),
    fetched_at    TIMESTAMPTZ DEFAULT NOW()
);
-- Widen older source columns if the column already existed at a narrower size.
ALTER TABLE ingest_audit ALTER COLUMN source TYPE VARCHAR(120);
"""


def apply_schema(dsn: str) -> None:
    """Apply the schema to the Postgres instance at `dsn`. Idempotent."""
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    logger.info("schema applied")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    apply_schema(str(settings.postgres_url))
    print("Schema applied. Run sanity checks:")
    print("  docker exec -it earningsrag-postgres psql -U earningsrag -d earningsrag -c '\\d chunks'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
