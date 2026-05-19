# Postgres + pgvector — Patterns

Reference for vector search in Postgres on this project. We run Postgres 16 with pgvector via docker compose locally.

## Why Postgres + pgvector and not a separate vector DB

One database means one transaction, one backup story, one connection pool, one auth model. The hybrid query — "filter on `ticker = 'AAPL' AND quarter = 'Q3'`, then vector-search the filtered set, then rerank" — is one SQL statement plus one Cohere call, not a two-system orchestration. At this project's scale (around 6000 chunks), pgvector is faster than the round-trip to a dedicated vector service. The interview answer is the same answer.

## Index choice: HNSW vs IVFFlat

| Index | When to use | Build time | Query time | Memory |
|---|---|---|---|---|
| **HNSW** | Default. Always use this for production. | Slow (minutes for 1M vectors; seconds for 6K) | Fast (sub-ms for top-K) | High |
| **IVFFlat** | Only if memory is constrained and HNSW won't fit. | Fast | Slower than HNSW, needs `lists` tuning | Lower |

Use HNSW. The build cost is paid once at ingest. Query latency wins.

```sql
CREATE INDEX chunks_embedding_idx
ON chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Tuning:

- `m` (default 16): graph connectivity. Higher = better recall, more memory. Stick with 16 for 1024-dim vectors.
- `ef_construction` (default 64): index build effort. Higher = better recall, slower build. 64 is fine for this project; bump to 200 if recall@5 is below 0.85.
- `hnsw.ef_search` (session-level, default 40): query-time effort. Set in your session for the rerank-first stage:

```sql
SET hnsw.ef_search = 100;
```

## Distance operators

pgvector exposes three operators:

| Operator | Distance | Use when |
|---|---|---|
| `<=>` | Cosine | **Default for embeddings.** Voyage embeddings are normalized; cosine and inner product converge. |
| `<#>` | Negative inner product | Faster than cosine. Use only if vectors are normalized (Voyage's are). |
| `<->` | Euclidean (L2) | Rarely the right choice for embeddings; use for spatial data. |

The index op-class must match: `vector_cosine_ops` for `<=>`, `vector_ip_ops` for `<#>`, `vector_l2_ops` for `<->`. Mismatched op-class = the index isn't used.

## Hybrid query patterns

### Pattern 1 — Filter then vector search (the project's main pattern)

The `(ticker, year, quarter)` filter is the most important access path. Always filter on it first when a query pins to a specific call.

```sql
-- 1) Filter to chunks from a specific call, 2) vector-search within them.
SELECT
  id,
  text,
  speaker_name,
  speaker_role,
  section,
  hedging_score,
  1 - (embedding <=> $1::vector) AS similarity
FROM chunks
WHERE ticker = $2
  AND year = $3
  AND quarter = $4
ORDER BY embedding <=> $1::vector
LIMIT 50;
```

For cross-company queries:

```sql
WHERE ticker = ANY($2::TEXT[])    -- e.g., ARRAY['AAPL','GOOGL']
  AND year = $3
```

Verify with `EXPLAIN`:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT ... FROM chunks WHERE ticker = 'AAPL' AND year = 2024 AND quarter = 'Q3' ...;
```

Look for `Bitmap Index Scan on chunks_ticker_idx` (or the year/quarter composite) in the plan. If you see `Seq Scan`, either the index is missing or the planner thinks the filter is too unselective.

### Pattern 2 — Hybrid BM25 + vector with reranking

For queries where the user might use exact phrases ("free cash flow", "Apple Intelligence", "data center capex") along with semantic intent, run BM25 and dense in parallel, merge, then rerank.

```sql
WITH bm25 AS (
  SELECT id, text, ts_rank(text_search, plainto_tsquery('english', $1)) AS score
  FROM chunks
  WHERE text_search @@ plainto_tsquery('english', $1)
    AND ticker = ANY($2::TEXT[])
  ORDER BY score DESC
  LIMIT 50
),
dense AS (
  SELECT id, text, 1 - (embedding <=> $3::vector) AS score
  FROM chunks
  WHERE ticker = ANY($2::TEXT[])
  ORDER BY embedding <=> $3::vector
  LIMIT 50
)
SELECT id, text FROM bm25
UNION
SELECT id, text FROM dense;
```

Pass the union (~50–100 candidates after dedup) to Cohere Rerank 3.5 with the user question. Keep the top 5–10.

### Pattern 3 — Hedging / topic filter

The Claude enrichment columns turn "show me the most evasive AI capex answers" into a one-line WHERE clause:

```sql
SELECT id, text, ticker, quarter, year, speaker_name, hedging_score
FROM chunks
WHERE topics @> ARRAY['AI capex']
  AND hedging_score >= 0.7
  AND section = 'qa'
  AND year = 2024
ORDER BY hedging_score DESC, embedding <=> $1::vector
LIMIT 10;
```

The `chunks_topics_gin_idx` GIN index makes the array containment cheap.

## Indexing checklist for this project

```sql
-- The main vector index
CREATE INDEX chunks_embedding_idx
ON chunks USING hnsw (embedding vector_cosine_ops);

-- Full-text search (BM25 path)
-- text_search column is GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX chunks_search_idx ON chunks USING gin (text_search);

-- Metadata pre-filters (the cheapest accuracy gains)
CREATE INDEX chunks_ticker_idx       ON chunks (ticker);
CREATE INDEX chunks_year_quarter_idx ON chunks (year, quarter);
CREATE INDEX chunks_speaker_role_idx ON chunks (speaker_role);

-- Topics array containment
CREATE INDEX chunks_topics_gin_idx ON chunks USING gin (topics);
```

## Anti-patterns

- **Calling `embedding = $1` instead of `embedding <=> $1::vector`.** Equality on vectors checks every component; you want distance.
- **Forgetting `::vector` cast.** pgvector won't auto-cast a Python list. Without the cast, you'll see "no operator matches" errors.
- **Filtering after `ORDER BY <=>`.** Postgres applies the order before the WHERE if the WHERE isn't index-friendly. Put the filter first; verify with EXPLAIN.
- **Using IVFFlat without recreating the index when the corpus grows.** IVFFlat's `lists` parameter is fixed at build time; a corpus 10x larger needs a rebuild. HNSW grows gracefully.
- **Skipping ANALYZE after bulk insert.** The query planner needs accurate statistics. Run `ANALYZE chunks` after the initial ingest.

## Cost asymmetry to remember (and quote in interviews)

Vector search over 6000 chunks (full corpus) = ~10 ms with HNSW.
Vector search over 70 chunks (ticker + year + quarter pre-filter) = ~1 ms.

That's roughly **10x** at this scale, growing to **4000x** if the corpus scales 100x. Metadata pre-filtering is the cheapest accuracy gain in RAG, and it's an even bigger win at scale.
