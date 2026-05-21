"""FastAPI backend for the Next.js UI.

Endpoints:
  POST /api/ask        — question + filters -> SynthesisResult
  GET  /api/companies  — corpus index ([ticker, year, quarter, n_chunks])
  GET  /api/speakers   — distinct (ticker, speaker_name, speaker_role) tuples
  GET  /api/chunks/:id — fetch one chunk by id (HoverCard quote lookup)
  GET  /api/health     — liveness ping

The Next.js dev server runs on port 3000; this API runs on 8000. CORS is
allowed for the dev origins; production deployment tightens this.

Run with:
  uv run uvicorn src.api.server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from src.config import get_settings
from src.retrieve.filters import RetrievalFilters
from src.synthesize.pipeline import ask as ask_pipeline

logger = logging.getLogger(__name__)

settings = get_settings()


app = FastAPI(
    title="Earnings Call Analyzer",
    version="0.1.0",
    description="Hybrid RAG over Mag 7 quarterly earnings call transcripts.",
)

# Allowed origins: local dev by default. In production set
# CORS_ALLOW_ORIGINS=https://<your-vercel-domain>,https://<another> as a
# comma-separated list, OR `*` for a fully public demo.
_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_env_origins = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
if _env_origins == "*":
    _allow_origins = ["*"]
elif _env_origins:
    _allow_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    _allow_origins = _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class AskRequest(BaseModel):
    """Body for POST /api/ask."""

    question: str = Field(..., min_length=1, max_length=2000)
    tickers: list[str] | None = None
    year: int | None = None
    quarter: str | None = None
    section: str | None = None
    speaker_roles: list[str] | None = None
    min_hedging_score: float | None = None
    topics: list[str] | None = None
    candidate_k: int = 50
    top_k: int = 10


class ChunkResponse(BaseModel):
    chunk_id: int
    rerank_score: float | None = None
    ticker: str
    company: str
    quarter: str
    year: int
    call_date: str
    speaker_name: str | None
    speaker_role: str | None
    section: str | None
    hedging_score: float | None
    sentiment: str | None
    topics: list[str] | None
    text: str


class CitationResponse(BaseModel):
    ticker: str
    quarter: str
    year: int
    speaker: str


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationResponse]
    chunks: list[ChunkResponse]
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


class CallSummary(BaseModel):
    ticker: str
    year: int
    quarter: str
    call_date: str
    company: str
    chunk_count: int


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/companies", response_model=list[CallSummary])
def companies() -> list[CallSummary]:
    """Return the index of available (ticker, year, quarter) calls."""
    with psycopg.connect(str(settings.postgres_url)) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT ticker, year, quarter, MIN(call_date) AS call_date,
                   MIN(company) AS company, COUNT(*) AS chunk_count
            FROM chunks
            GROUP BY ticker, year, quarter
            ORDER BY ticker, year, quarter
            """
        )
        rows = cur.fetchall()
    return [
        CallSummary(
            ticker=str(r["ticker"]),
            year=int(r["year"]),
            quarter=str(r["quarter"]),
            call_date=str(r["call_date"]),
            company=str(r["company"]),
            chunk_count=int(r["chunk_count"]),
        )
        for r in rows
    ]


@app.get("/api/chunks/{chunk_id}", response_model=ChunkResponse)
def chunk(chunk_id: int) -> ChunkResponse:
    """Fetch one chunk by ID; used by citation chips on hover."""
    with psycopg.connect(str(settings.postgres_url)) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id, ticker, company, quarter, year, call_date,
                   speaker_name, speaker_role, section,
                   hedging_score, sentiment, topics, text
            FROM chunks WHERE id = %s
            """,
            (chunk_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, detail=f"chunk {chunk_id} not found")
    return ChunkResponse(
        chunk_id=int(row["id"]),
        rerank_score=None,
        ticker=str(row["ticker"]),
        company=str(row["company"]),
        quarter=str(row["quarter"]),
        year=int(row["year"]),
        call_date=str(row["call_date"]),
        speaker_name=row.get("speaker_name"),
        speaker_role=row.get("speaker_role"),
        section=row.get("section"),
        hedging_score=row.get("hedging_score"),
        sentiment=row.get("sentiment"),
        topics=list(row["topics"]) if row.get("topics") else None,
        text=str(row["text"]),
    )


def _session_id_from_request(request: Request) -> str:
    """Pin the per-session cost ceiling to the caller's IP.

    Railway routes through an edge proxy, so prefer the leftmost
    X-Forwarded-For entry; fall back to the direct connection if the header
    is absent (local dev, curl).
    """
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client is not None:
        client_ip = request.client.host
    else:
        client_ip = "unknown"
    return f"ip:{client_ip}"


@app.post("/api/ask", response_model=AskResponse)
async def ask(req: AskRequest, request: Request) -> AskResponse:
    """Run the full retrieve + synthesize pipeline and return a cited answer."""
    from anthropic import AsyncAnthropic

    filters = RetrievalFilters(
        tickers=req.tickers,
        year=req.year,
        quarter=req.quarter,
        section=req.section,
        speaker_roles=req.speaker_roles,
        min_hedging_score=req.min_hedging_score,
        topics=req.topics,
    )
    anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())

    with psycopg.connect(str(settings.postgres_url)) as conn:
        result = await ask_pipeline(
            question=req.question,
            conn=conn,
            anthropic_client=anthropic_client,
            voyage_api_key=settings.voyage_api_key.get_secret_value(),
            cohere_api_key=settings.cohere_api_key.get_secret_value(),
            filters=filters,
            candidate_k=req.candidate_k,
            top_k=req.top_k,
            session_id=_session_id_from_request(request),
        )

    return AskResponse(
        question=result.question,
        answer=result.answer,
        citations=[
            CitationResponse(ticker=c.ticker, quarter=c.quarter, year=c.year, speaker=c.speaker)
            for c in result.citations
        ],
        chunks=[
            ChunkResponse(
                chunk_id=c.chunk_id,
                rerank_score=c.rerank_score,
                ticker=c.ticker,
                company=c.company,
                quarter=c.quarter,
                year=c.year,
                call_date=c.call_date,
                speaker_name=c.speaker_name,
                speaker_role=c.speaker_role,
                section=c.section,
                hedging_score=c.hedging_score,
                sentiment=c.sentiment,
                topics=c.topics,
                text=c.text,
            )
            for c in result.chunks_used
        ],
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )
