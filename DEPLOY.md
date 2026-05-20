# Deploy guide — Earnings Call Analyzer

This document is the end-to-end checklist for taking the local app to a public
demo. Total time: about **90 minutes**, most of which is account signups and
the one-time data migration.

Architecture going to production:

```
┌─────────────────┐    HTTPS   ┌──────────────────────┐    Postgres    ┌──────────────┐
│  Next.js (UI)   │ ────────▶  │  FastAPI (backend)   │ ─────────────▶ │  Neon DB     │
│  on Vercel      │            │  on Railway          │                │  pgvector    │
└─────────────────┘            └──────────────────────┘                └──────────────┘
                                          │
                                          └─► Anthropic, Voyage, Cohere APIs
```

## 0. Prerequisites

You'll need accounts at:

- [Neon](https://neon.tech) — managed Postgres with pgvector (free tier covers this project)
- [Railway](https://railway.app) — backend host (Hobby plan, $5/month, supports long requests)
- [Vercel](https://vercel.com) — frontend host (free)
- API keys you already have locally in `.env`: `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY`, optional `BRAINTRUST_API_KEY`

> Why not Fly.io or Render free? Render free sleeps after 15 min of inactivity (30 s cold start kills the demo); Fly.io free tier (256 MB RAM) is tight for the synthesis path. Railway's $5/mo Hobby is the most reliable for this use case.

## 1. Neon — provision the database (≈ 10 min)

1. Sign up at [neon.tech](https://neon.tech) and create a new **Project**. Name it `earnings-rag`.
2. Choose any region (pick the one closest to your Railway region; if unsure, **us-east-2** is a good default).
3. Once the project is created, copy the **connection string** from the dashboard. It looks like:
   ```
   postgresql://<user>:<password>@ep-foo-bar-12345.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
4. In the Neon SQL Editor, run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   This enables pgvector. Neon supports it out of the box; you just need to flip it on per project.

Save the connection string — you'll use it for the migration and for Railway.

## 2. Migrate the corpus to Neon (≈ 5 min)

Make sure your local Docker Postgres is running (`docker compose ps` shows the container healthy), then from the repo root on Windows PowerShell:

```powershell
$env:LOCAL_POSTGRES_URL = "postgresql://earningsrag:earningsrag@localhost:5433/earningsrag"
$env:NEON_POSTGRES_URL  = "postgresql://...your Neon URL..."
uv run python -m scripts.migrate_to_neon
```

What this does (see `scripts/migrate_to_neon.py`):

1. Enables `vector` on the destination (in case step 1 was skipped).
2. Applies the canonical schema (creates `chunks` and `ingest_audit` tables + all indexes).
3. Streams every row from your local DB into Neon in 64-row batches.
4. Verifies counts match before exiting.

Expected output: `Done. 1097 chunks now live on Neon.` (or whatever your current corpus size is).

## 3. Railway — deploy the FastAPI backend (≈ 15 min)

1. Sign up at [railway.app](https://railway.app) with your GitHub account.
2. Click **New Project** → **Deploy from GitHub repo** → pick `ZayM511/Earnings-Call-Analyzer-RAG-Pipeline`.
3. Railway will detect Python and start building from the `nixpacks.toml` and `railway.json` already in the repo. The start command is `uvicorn src.api.server:app --host 0.0.0.0 --port $PORT`.
4. While the build is running, open the project → **Variables** tab and add:

   | Variable | Value |
   |---|---|
   | `POSTGRES_URL` | The Neon connection string from step 1 |
   | `ANTHROPIC_API_KEY` | Same value as your local `.env` |
   | `VOYAGE_API_KEY` | Same |
   | `COHERE_API_KEY` | Same |
   | `BRAINTRUST_API_KEY` | Optional — leave blank to disable tracing |
   | `BRAINTRUST_PROJECT` | `earnings-rag` |
   | `CORS_ALLOW_ORIGINS` | Set to `*` for the first deploy. After you have a Vercel URL (step 4), tighten to that exact domain. |
   | `LOG_LEVEL` | `INFO` |

5. Once the build finishes, click **Settings** → **Networking** → **Generate Domain**. You'll get a URL like `earnings-call-analyzer-rag-pipeline-production.up.railway.app`.
6. Smoke-test it from your browser: `https://<your-railway-url>/api/health` → should return `{"status":"ok"}`.
7. Smoke-test the corpus index: `https://<your-railway-url>/api/companies` → should return a JSON array of 41 calls.

> Why Hobby plan? Synthesis takes 20–40 seconds per query. Free Railway accounts have a 5-minute cap on builds and aggressive sleep behaviour; Hobby gives you a real always-on container for $5/mo.

## 4. Vercel — deploy the Next.js frontend (≈ 10 min)

1. Sign up at [vercel.com](https://vercel.com) with your GitHub account.
2. Click **Add New** → **Project** → import `ZayM511/Earnings-Call-Analyzer-RAG-Pipeline`.
3. **Critical setting**: under **Root Directory**, click **Edit** and set it to `ui` (not the repo root). Vercel will then detect Next.js 16 + Tailwind v4 automatically.
4. Expand **Environment Variables** and add:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE` | The Railway URL from step 3, e.g. `https://earnings-call-analyzer-rag-pipeline-production.up.railway.app` (no trailing slash) |

5. Click **Deploy**. First build takes ~2 minutes.
6. When the deploy goes green, click **Visit** to open your live site. Copy the domain (e.g. `earnings-call-analyzer-rag-pipeline.vercel.app`).

## 5. Tighten CORS (≈ 2 min)

Go back to Railway → Variables, find `CORS_ALLOW_ORIGINS`, and replace `*` with your Vercel domain:

```
https://earnings-call-analyzer-rag-pipeline.vercel.app
```

Railway will redeploy automatically. The backend now only accepts requests from your Vercel domain.

## 6. Verify the live demo (≈ 5 min)

Open your Vercel URL and run through the four sample chips on the landing page:

- **Vision Pro adoption on AAPL Q4 2024** — should return a cited answer in ~20 s
- **MSFT AI capex framing over time** — should return citations across Q3 2024 through Q1 2026
- **Apple vs Google on China risk** — single-call mode answers from Apple's calls
- **Evasive CEO answers in 2024** — should surface high-hedging-score chunks

Also test:

- Toggle to dark mode via the Sun/Moon button (top right). Persists on reload.
- Navigate to **Compare** and run a 3-column comparison. Each column should trace independently and finalize with its own cited answer.
- Navigate to **How I Made This** and confirm the architecture diagram + 11 build steps + commit links all render.

## Costs while running

| Service | Plan | Monthly cost |
|---|---|---|
| Neon | Free | $0 |
| Railway | Hobby | $5 |
| Vercel | Hobby | $0 |
| Anthropic / Voyage / Cohere | Pay per query | ~$0.10 per question, capped per session via `SESSION_COST_CEILING_USD` |

**Idle cost**: ~$5/month. **Per-query cost**: well under $1 even for the largest comparison.

## Troubleshooting

**Railway build fails on `pip install`**
→ Check the build log. Most often the cause is missing system libs; `nixpacks.toml` already pins `gcc` for the `psycopg` C extension. If you see `pgvector` import errors, ensure the `vector` extension is enabled on Neon (step 1).

**Frontend loads but Ask returns "Failed to fetch"**
→ Open browser devtools → Network → click the failed `/api/ask` call. If you see a CORS error, your Railway `CORS_ALLOW_ORIGINS` doesn't match your Vercel domain exactly (check for `https://` and no trailing slash). If you see 502/503, Railway is asleep — wake it via `/api/health`.

**Citation chips work but the answer text is blank**
→ Look at the Railway logs while a query is running. The most common cause is `POSTGRES_URL` pointing at a DB that doesn't have the corpus loaded — re-run step 2.

**Synthesis times out (Vercel error)**
→ Vercel Hobby has no timeout on Next.js routes (only on serverless functions). Since the synthesis happens on Railway and the frontend just `fetch`-es, you should be fine. If you see timeouts in production, check Railway's resource graph for memory pressure (256 MB containers can OOM on large queries).

## Automated redeploys

After the initial setup, the deploy pipeline is fully automatic:

- **Push to `main`** triggers a Railway rebuild (backend) and a Vercel rebuild (frontend) in parallel.
- Both deploy in under 3 minutes.
- Railway preserves the DB across deploys (it's on Neon, not Railway).
- Vercel keeps history of every deploy so you can roll back instantly from the dashboard.
