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

(eval pending — runs after ingestion completes)

The 30-query Braintrust eval set is stratified across three query types:

| Type | Cases | What it tests |
|---|---|---|
| `single_call` | 10 | Retrieval pinned to ticker + year + quarter; precision on exact-call lookup |
| `multi_quarter` | 10 | Temporal synthesis across 8 quarters; tone and topic drift over time |
| `cross_company` | 10 | Comparing two or more tickers on a shared topic |

The README will publish three experiment screenshots once the pipeline lands:

1. `voyage-finance-2` vs `voyage-3-large` (expect finance-tuned to win)
2. With Cohere Rerank vs without (expect ~15–20 point recall@5 improvement)
3. With hedging-score metadata pre-filter vs without (expect higher precision on evasiveness queries)

## Security

- OWASP LLM Top 10 (2025) as the framework — see [SECURITY.md](./SECURITY.md).
- Every retrieved chunk treated as untrusted; instruction-like phrases stripped before the synthesis prompt (`src/guardrails.py::sanitize_retrieved_chunk`).
- Per-query token cap (8K in / 2K out), per-session cost ceiling ($0.50), hourly aggregate circuit breaker ($5), model cascade Haiku → Sonnet → Opus.
- Every API key in `.env` (gitignored). The `block-secrets.sh` PreToolUse hook blocks any commit that contains a key matching common patterns.
- Postgres MCP server uses a read-only role enforced at the DB engine, not just in application code. Verified: the role can `SELECT` but `INSERT` errors with permission denied.

## What I tried and rejected

- **Fixed-character chunking.** The tutorial default. Tried it on a single Apple call as a smoke test, then dropped it — paragraph cuts mid-sentence destroyed the Q&A → answer pairing that makes the corpus useful. Speaker-aware chunking with a 200-token floor preserves the structure.
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

# 5. (next phase) Ingest the 56 Mag 7 transcripts.
uv run python -m src.ingest --all-mag7

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
│   ├── ingest/                HF datasets + Motley Fool scraper
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
