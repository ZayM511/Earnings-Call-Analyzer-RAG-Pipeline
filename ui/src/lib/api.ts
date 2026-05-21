/**
 * Typed client for the FastAPI backend.
 *
 * URL resolution precedence:
 *   1. NEXT_PUBLIC_API_BASE env var (explicit override)
 *   2. Railway production URL (when NODE_ENV=production, i.e. Vercel build)
 *   3. http://localhost:8001 (local `next dev`; 8000 is the sibling NBA project)
 *
 * Override via ui/.env.local for a staging backend or alternate local port.
 */

const PRODUCTION_API =
  "https://earnings-call-analyzer-rag-pipeline-production.up.railway.app";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  (process.env.NODE_ENV === "production"
    ? PRODUCTION_API
    : "http://localhost:8001");

export interface Citation {
  ticker: string;
  quarter: string;
  year: number;
  speaker: string;
}

export interface Chunk {
  chunk_id: number;
  rerank_score: number | null;
  ticker: string;
  company: string;
  quarter: string;
  year: number;
  call_date: string;
  speaker_name: string | null;
  speaker_role: string | null;
  section: string | null;
  hedging_score: number | null;
  sentiment: string | null;
  topics: string[] | null;
  text: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  citations: Citation[];
  chunks: Chunk[];
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface CallSummary {
  ticker: string;
  year: number;
  quarter: string;
  call_date: string;
  company: string;
  chunk_count: number;
}

export interface AskRequest {
  question: string;
  tickers?: string[];
  year?: number;
  quarter?: string;
  section?: string;
  speaker_roles?: string[];
  min_hedging_score?: number;
  topics?: string[];
  candidate_k?: number;
  top_k?: number;
}

export async function ask(req: AskRequest): Promise<AskResponse> {
  const resp = await fetch(`${API_BASE}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`ask failed: ${resp.status} ${text}`);
  }
  return resp.json();
}

export async function fetchCompanies(): Promise<CallSummary[]> {
  const resp = await fetch(`${API_BASE}/api/companies`, {
    cache: "no-store",
  });
  if (!resp.ok) throw new Error(`companies failed: ${resp.status}`);
  return resp.json();
}

export async function fetchChunk(chunkId: number): Promise<Chunk> {
  const resp = await fetch(`${API_BASE}/api/chunks/${chunkId}`);
  if (!resp.ok) throw new Error(`chunk ${chunkId} failed: ${resp.status}`);
  return resp.json();
}
