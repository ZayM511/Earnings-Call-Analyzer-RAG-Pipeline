# postgres (MCP)

Community Postgres MCP server. Direct read-only query access to the project DB so Claude Code can inspect chunks, run sanity checks, and verify schema state without copy-pasting psql output. Major productivity multiplier for a Postgres-heavy project.

## Config (in .mcp.json)

```json
"postgres": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "${env:POSTGRES_READONLY_URL}"
  ]
}
```

The connection string comes from `POSTGRES_READONLY_URL`. See `.env.example` for the format.

## Connection string format

```
postgresql://<readonly_user>:<password>@<host>:<port>/<database>
```

Example for local dev:

```
postgresql://earningsrag_readonly:earningsrag_readonly@localhost:5433/earningsrag
```

For Neon or another hosted Postgres, the URL will include `?sslmode=require`.

## READ-ONLY role enforcement (critical)

The connection string must point at a user who has `SELECT` privileges only. The role is created automatically by `docker/initdb/02_readonly_role.sql` on first container startup:

```sql
CREATE ROLE earningsrag_readonly WITH LOGIN PASSWORD 'earningsrag_readonly';
GRANT CONNECT ON DATABASE earningsrag TO earningsrag_readonly;
GRANT USAGE ON SCHEMA public TO earningsrag_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO earningsrag_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO earningsrag_readonly;
```

This is belt-and-suspenders with the `security-reviewer` agent. The agent rejects DDL/DML on review; the DB role rejects it at execution. Both layers must hold.

## Tools it exposes

- `query` — run a SQL query, return rows.
- `list_schemas`, `list_tables`, `describe_table` — schema inspection.

That's basically it. The MCP server is intentionally narrow; it's a structured way to run read-only SQL.

## Sample queries Claude Code might run for sanity checking

### "Did all 56 transcripts ingest cleanly?"

```sql
SELECT ticker, year, quarter, COUNT(*) AS chunk_count
FROM chunks
GROUP BY ticker, year, quarter
ORDER BY ticker, year, quarter;
```

Should return 56 rows (7 tickers × 8 quarters). Any missing combination is an ingestion gap.

### "Is the HNSW index actually being used by the planner?"

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, text, ticker, quarter, year
FROM chunks
WHERE ticker = 'AAPL' AND year = 2024 AND quarter = 'Q3'
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

Look for `Index Scan using chunks_embedding_idx` in the plan. If you see `Seq Scan`, the index is missing or the planner thinks the corpus is small enough that scanning is cheaper (which means we have less data than expected).

### "How is hedging distributed by section?"

```sql
SELECT
  section,
  ROUND(AVG(hedging_score)::numeric, 3) AS avg_hedging,
  COUNT(*) AS n
FROM chunks
GROUP BY section;
```

Q&A should have a higher average than prepared. If they're the same, the Sonnet enrichment isn't differentiating, and the prompt needs tuning.

### "Which speakers appear most often, and as what role?"

```sql
SELECT
  speaker_name,
  speaker_role,
  COUNT(DISTINCT (ticker, year, quarter)) AS calls,
  COUNT(*) AS chunks
FROM chunks
WHERE speaker_name IS NOT NULL
GROUP BY speaker_name, speaker_role
ORDER BY chunks DESC
LIMIT 30;
```

Catches role-classification bugs. If "Tim Cook" appears as both `CEO` and `Other`, the heuristic needs a fix.

### "Do all chunks have non-empty text and a valid embedding?"

```sql
SELECT
  COUNT(*) FILTER (WHERE text IS NULL OR LENGTH(text) = 0) AS empty_text,
  COUNT(*) FILTER (WHERE embedding IS NULL) AS missing_embedding,
  COUNT(*) AS total
FROM chunks;
```

Should be `(0, 0, ~6000)`. Anything else is a pipeline gap.

## When to use vs the application code

Use the MCP server for **inspection and sanity checks** during dev. Use the application code (`src/retrieve/`, `src/synthesize/`) for anything that runs in production.

The MCP server is not in the runtime hot path; the application connects with its own connection pool. The MCP server is for the developer (you and Claude Code) to poke around.

## Cost / safety notes

- The read-only role is the single most important defense. Verify it works:

```sql
-- Connect as earningsrag_readonly and run:
INSERT INTO chunks (text, ticker, quarter, year, embedding) VALUES ('test', 'TEST', 'Q1', 2024, NULL);
-- Should error: ERROR:  permission denied for table chunks
```

- Never set the MCP server's connection string to the application's write role.
- If the project ever serves multiple users (multi-tenant demo), give each tenant a separate role with row-level security; don't share the readonly role.
