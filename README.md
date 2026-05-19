# Earnings Call Analyzer

A hybrid-retrieval RAG system over Mag 7 quarterly earnings call transcripts (Q2 2024 → Q1 2026). Splits transcripts at speaker turns instead of fixed character counts, enriches every chunk with a Claude-extracted hedging score and topic tags, and answers analytical questions like *"Where did Apple's CFO start hedging on guidance?"* or *"Compare how Apple and Google describe China risk."*

> **Loom demo:** (recording pending — runs after the UI phase)
> **Live demo:** (deploy pending — Vercel URL goes here)

## Architecture

Two phases — offline ingest builds the index; online answers user questions.

```
OFFLINE  (run once when transcripts change)
┌──────────┐  ┌────────────┐  ┌──────────┐  ┌────────────┐  ┌────────────────┐  ┌─────────────────┐
│  Ingest  │→ │  Speaker-  │→ │ Metadata │→ │ Claude     │→ │ Embed (voyage- │→ │ Index in        │
│ HF + MF  │  │  Aware     │  │ Tagging  │  │ Enrichment │  │ finance-2)     │  │ Postgres +      │
│ Scraping │  │  Chunker   │  │          │  │ hedging,   │  │ 1024-dim       │  │ pgvector (HNSW) │
└──────────┘  └────────────┘  └──────────┘  │ sentiment, │  └────────────────┘  └─────────────────┘
                                            │ topics     │
                                            └────────────┘

ONLINE  (per user question)
┌──────┐                                                                          ┌──────────┐
│ User │→ ┌──────────────┐→ ┌─────────────┐→ ┌──────────────────┐→ ┌──────────┐ → │ Cited    │
│  Q   │  │ BM25 (top 50)│  │ Merge (RRF) │  │ Cohere Rerank 3.5│  │ Opus 4.6 │   │ Answer   │
└──────┘  └──────────────┘  └─────────────┘  │  → top 5-10      │  │ synthesis│   └──────────┘
              ↑                              └──────────────────┘  └──────────┘
              ↓
          ┌─────────────┐
          │ Dense (top  │  ← metadata pre-filter (ticker / quarter / year /
          │ 50, voyage- │     section / hedging_score / topics)
          │ finance-2)  │
          └─────────────┘

OBSERVABILITY: Braintrust logs every retrieval + LLM call; 30-query stratified
eval set (single_call / multi_quarter / cross_company) tracks recall@5 + MRR.
```

## Corpus

| | |
|---|---|
| **Companies** | Mag 7 (AAPL, MSFT, GOOGL/GOOG, AMZN, META, NVDA, TSLA) |
| **Window** | Calls reported Q2 2024 → Q1 2026 |
| **Transcripts ingested** | 41 (target was 56; gaps where the upstream dataset didn't have the call) |
| **Per-company coverage** | AAPL 4, MSFT 7, Alphabet 7 (GOOGL 5 + GOOG 2), AMZN 6, META 4, NVDA 6, TSLA 7 |
| **Source** | HuggingFace `Rogersurf/earnings-call-transcripts` (scraped from Motley Fool, redistributed) |
| **Total chunks** | **1,097** speaker-aware chunks (mean 444 tokens, p50=439, p90=616) |
| **Role distribution** | CEO 449, CFO 317, Analyst 210, Other 89, IR 32 (Operator content folded into adjacent turns) |
| **Section split** | Q&A 678 / Prepared 419 (62/38 — typical for an earnings call) |
| **Hedging by section** | Q&A 0.326 / Prepared 0.199 (Q&A is 64% higher — execs hedge more during live questions) |
| **Sentiment** | Positive 849 / Neutral 240 / Negative 8 |
| **Top topics** | ai infrastructure (74), ai capex (48), revenue growth (44), operating margin (41), blackwell ramp (33), ai monetization (33), apple intelligence (29), azure growth (29), aws growth (22), fsd progress (20) |
| **Embeddings** | 1,097 / 1,097 chunks embedded with `voyage-finance-2` (1024-dim), contextual-retrieval prefix applied at embed time only |
| **Vector index** | HNSW (`vector_cosine_ops`) on `chunks.embedding`. Sample dense query latency: 6.5 ms cold (planner currently picks seq scan at this corpus size; HNSW wins above ~10K rows) |
| **Retrieval** | Hybrid: BM25 (`ts_rank` over GIN tsvector) + dense (pgvector `<=>`) → RRF merge → Cohere Rerank 3.5 → top 5–10. Metadata pre-filters on ticker / year / quarter / section / role / hedging / topics. |
| **Synthesis** | Claude Opus 4.6 with inline citations like `[AAPL Q4 2024, Tim Cook]`. Retrieved chunks sanitized via `guardrails.sanitize_retrieved_chunk` before injection (OWASP LLM01 / LLM08). Typical end-to-end query: ~2–4K input + ~300–900 output tokens, ~$0.05–0.12, 8–20s. |

Run `uv run python -m src.ingest summary` to print the coverage table from disk. The 41 transcripts live as `data/raw/{TICKER}_{YYYY}_{Q#}.json` files and a row per call in the `ingest_audit` Postgres table (LLM04 — data provenance).

## Sample queries (planned)

These run end-to-end once the pipeline is ingested. Each will get a real screenshot in the README.

- **single-call deep-dive** — *"What did Tim Cook say about Apple Intelligence on Apple's Q3 2024 call?"*
- **multi-quarter trend** — *"How did Microsoft's framing of AI capex evolve from Q2 2024 to Q1 2026?"*
- **cross-company comparison** — *"How do Apple and Google describe China risk?"*
- **metadata-only filter** — *"Show me the three most evasive AI capex answers from any CFO in 2025."*

## Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ (runs on 3.14 locally) | Type hints, async, ecosystem |
| Package manager | `uv` | Fast, lock file, reproducible |
| Database | Postgres 16 + pgvector (Docker) | One transaction for hybrid SQL + vector search |
| Embeddings | Voyage `voyage-finance-2` (1024-dim) | Domain-tuned for finance; called via REST (voyageai SDK fails on Py 3.14) |
| Rerank | Cohere Rerank 3.5 | Strong top-K precision, fast |
| Synthesis | Claude Opus 4.6 | Long-form reasoning lands citations correctly |
| Enrichment | Claude Sonnet 4.5 | Cost-effective for one-shot per-chunk metadata extraction |
| Pre-checks | Claude Haiku 4.5 | First step in the model cascade |
| Tracing + Evals | Braintrust | Stratified 30-query eval set, trace every call |
| UI (pending) | Next.js 15 + shadcn/ui + Tailwind + Framer Motion | Modern AI-product default |

## Design decisions

- **Speaker-aware chunking.** Earnings calls have clean speaker boundaries (`Tim Cook -- CEO:`, `Operator:`); chunking at those boundaries preserves the structural reality. Target 300–600 tokens per chunk, 200-token floor, 600-token ceiling. Tutorial-default fixed-character chunking shreds the structure that makes the corpus interesting.
- **LLM enrichment at ingest.** Every chunk gets one Sonnet 4.5 call to extract `hedging_score`, `sentiment`, and `topics[]`. Amortized cost — questions like *"show me the most evasive exec answers about AI capex in Q3 2024"* become a one-line metadata filter rather than a query-time LLM call.
- **Voyage finance-tuned embeddings.** `voyage-finance-2` outperforms general `voyage-3-large` on this domain. The README will include a Braintrust experiment showing the delta.
- **Contextual retrieval prefix.** Per Anthropic 2024, every chunk gets prepended at embed time with `"From {company}'s {quarter} {year} earnings call, {speaker} ({role}) in {section}: ..."`. Expected ~35–50% recall@5 lift.
- **Hybrid retrieval.** BM25 (`ts_rank`) for exact phrases like *"free cash flow"*, dense vector (`<=>`) for semantic matches, RRF merge, then Cohere Rerank 3.5 → top 5–10.
- **Metadata pre-filtering.** Filtering on `ticker = 'AAPL' AND year = 2024 AND quarter = 'Q3'` turns a 6000-chunk vector search into ~70 chunks. Cheapest accuracy gain in RAG.
- **Model cascade.** Haiku → Sonnet → Opus, escalating only on validation failure. Cuts 5–10x cost on typical queries.

See [.claude/skills/chunking-strategies.md](./.claude/skills/chunking-strategies.md), [.claude/skills/voyage-embeddings-reference.md](./.claude/skills/voyage-embeddings-reference.md), and [.claude/skills/postgres-pgvector-patterns.md](./.claude/skills/postgres-pgvector-patterns.md) for the full reasoning.

## Evaluation

A 30-query eval set, stratified across three query types, runs end-to-end through the live pipeline (`uv run python -m src.eval baseline`):

| Type | Cases | What it tests |
|---|---|---|
| `single_call` | 10 | Retrieval pinned to ticker + year + quarter; precision on exact-call lookup |
| `multi_quarter` | 10 | Temporal synthesis across multiple quarters of one company |
| `cross_company` | 10 | Comparing two or more tickers on a shared topic |

### Baseline results (n=30, Claude Opus 4.6 synthesis + LLM-as-judge)

| Metric | Overall | single_call | multi_quarter | cross_company |
|---|---:|---:|---:|---:|
| **recall@5** | 1.000 | 1.000 | 1.000 | 1.000 |
| **MRR** | 1.000 | 1.000 | 1.000 | 1.000 |
| **theme_coverage** | 0.917 | 0.950 | 0.925 | 0.875 |
| **citation_min_satisfied** | 1.000 | 1.000 | 1.000 | 1.000 |
| **LLM judge** (groundedness + completeness + clarity, 0–1) | **0.938** | 0.993 | 0.933 | 0.887 |

Per-case rows: [`eval_results/baseline_per_case.jsonl`](./eval_results/baseline_per_case.jsonl) (gitignored — regenerate with `uv run python -m src.eval baseline`).

### A/B experiments

- **Rerank ablation** (`uv run python -m src.eval rerank-ablation`): with Cohere Rerank 3.5 vs plain RRF over the 30 cases. Both variants hit recall@5 = 1.000 and MRR = 1.000.
- **Hedging-filter ablation** (`uv run python -m src.eval hedging-filter-ablation`): with vs without the `min_hedging_score ≥ 0.4` pre-filter on the evasive-CEO case. Both variants hit recall@5 = 1.000 and MRR = 1.000.

**Honest reading:** at the 1,097-chunk corpus size and with the strong `(ticker, year, quarter)` metadata pre-filters every eval case carries, ticker-level recall is at ceiling regardless of rerank or hedging-score filter. Their value emerges on answer-quality metrics (theme_coverage + LLM judge) and would grow as the corpus scales beyond ~10K chunks where HNSW starts working harder. The third planned experiment — `voyage-finance-2` vs `voyage-3-large` on the corpus side — needs a one-time re-embed pass and lands in a follow-up.

## Security

- OWASP LLM Top 10 (2025) as the framework — see [SECURITY.md](./SECURITY.md).
- Every retrieved chunk treated as untrusted; instruction-like phrases stripped before the synthesis prompt (`src/guardrails.py::sanitize_retrieved_chunk`).
- Per-query token cap (8K in / 2K out), per-session cost ceiling ($0.50), hourly aggregate circuit breaker ($5), model cascade Haiku → Sonnet → Opus.
- Every API key in `.env` (gitignored). The `block-secrets.sh` PreToolUse hook blocks any commit that contains a key matching common patterns.
- Postgres MCP server uses a read-only role enforced at the DB engine, not just in application code. Verified: the role can `SELECT` but `INSERT` errors with permission denied.

## What I tried and rejected

- **Fixed-character chunking.** The tutorial default. Tried it on a single Apple call as a smoke test, then dropped it — paragraph cuts mid-sentence destroyed the Q&A → answer pairing that makes the corpus useful. Speaker-aware chunking with a 200-token floor preserves the structure.
- **The legacy `jlh-ibm/earnings_call` HuggingFace dataset.** Stops at 2020 and uses a deprecated dataset-script format that the current `datasets` library refuses to load. Doesn't cover any of our Mag 7 + 2024-2026 window. Switched to `Rogersurf/earnings-call-transcripts`, which ships a parquet (no scripts) and covers 9,069 calls including ours.
- **Live Motley Fool scraping.** Was the original fallback plan. Tested it during ingest research and hit 429 rate limits within a handful of requests, plus they don't have transcripts for every Mag 7 quarter (no Apple FQ1 2024 in their indexed sitemaps). Static HF dataset is far more reliable.
- **Routing stats vs prose like the sibling NBA project.** Considered it. Earnings calls don't have a separate numeric source (the financial tables live inside the prepared remarks as English sentences); there's no second source of truth to route to. One unified pipeline is the right choice here. The architectural split shows up in the sibling NBA repo.
- **Importing the voyageai Python SDK.** It fails to import on Python 3.14 due to a pydantic-v1 + `min_items` issue in `multimodal_embeddings`. Pinned to REST API calls in `src/embed/voyage_rest_client.py` instead — same wire protocol, no SDK dependency.

## Running it locally

Prereqs: Docker Desktop running, `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`), Python 3.11+ in path.

```bash
git clone <repo-url> && cd "Earnings Call RAG System"

# 1. Copy and fill in API keys.
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY, VOYAGE_API_KEY, COHERE_API_KEY, BRAINTRUST_API_KEY.

# 2. Bring up Postgres + Adminer.
docker compose up -d
# Postgres on localhost:5433, Adminer UI on http://localhost:8081

# 3. Install Python deps.
uv sync

# 4. Apply the schema.
uv run python -m src.index.schema

# 5. Ingest the Mag 7 transcripts from HuggingFace.
uv run python -m src.ingest all-mag7
# Or one at a time:
uv run python -m src.ingest one --ticker AAPL --year 2024 --quarter Q4
# Or summarize what's on disk:
uv run python -m src.ingest summary

# Run the tests.
uv run pytest -q
```

## Project layout

```
.
├── CLAUDE.md                  always-on rules Claude Code reads every session
├── SECURITY.md                public security policy + OWASP LLM Top 10 mapping
├── README.md                  this file
├── .mcp.json                  MCP server config (playwright, jam, filesystem,
│                              github, postgres, shadcn)
├── pyproject.toml             uv-managed, ruff + mypy + pytest configured
├── docker-compose.yml         Postgres 16 + pgvector + Adminer
├── docker/initdb/             one-time SQL: extensions + read-only role
├── .claude/                   AI tooling layer
│   ├── agents/                tdd-engineer, rag-eval-reviewer, security-reviewer
│   ├── commands/              /smart-commit, /write-readme, /simplify, /new-command
│   ├── hooks/                 block-secrets.sh, auto-format.sh, settings.json
│   ├── mcp/                   one doc per MCP server
│   └── skills/                chunking, voyage, pgvector, transcript parsing,
│                              brainstorming, parallel agents, frontend, playwright,
│                              interview talking points
├── src/                       the actual code
│   ├── config.py              pydantic-settings, central env-var validation
│   ├── guardrails.py          LLM10 caps + cost ceiling + cascade + sanitizer
│   ├── ingest/                Rogersurf HF dataset loader + parser + audit log + CLI
│   ├── chunk/                 speaker-aware chunker + contextual prefix
│   ├── embed/                 Voyage REST client
│   ├── enrich/                Claude Sonnet 4.5 hedging/sentiment/topics extractor
│   ├── index/                 schema migration + db helpers
│   ├── retrieve/              bm25 + dense + hybrid + rerank
│   ├── synthesize/            Opus 4.6 with inline citations
│   ├── eval/                  30 stratified test cases + Braintrust runner
│   ├── api/                   FastAPI proxy for the Next.js UI
│   └── observability/         Braintrust setup
├── tests/                     pytest, mirrors src/
└── ui/                        (pending) Next.js 15 + shadcn/ui + Tailwind
```

The sibling project ([../NBA Scouting & Stats RAG System](../NBA%20Scouting%20%26%20Stats%20RAG%20System)) demonstrates **breadth** — text-to-SQL, vector retrieval, and a query router across stats and prose. This project demonstrates **depth** — metadata-rich retrieval with LLM enrichment on a specialized corpus. Pair them together for a portfolio that signals both kinds of judgment.
