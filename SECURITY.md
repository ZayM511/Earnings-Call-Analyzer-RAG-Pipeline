# Security Policy

This project is a public portfolio RAG system that ingests quarterly earnings call transcripts for the Mag 7 (Q2 2024 → Q1 2026) and answers natural-language questions over them. The security posture below reflects how the system handles untrusted input, model output, and cost.

## Scope

What this policy covers:

- The Python pipeline under `src/` (ingestion, chunking, enrichment, retrieval, synthesis, evaluation).
- The Next.js UI when it ships.
- The Postgres + pgvector database schema and query patterns.
- Every prompt sent to a Claude or Voyage or Cohere endpoint.
- Every chunk retrieved from the vector store.

Out of scope:

- The third-party APIs we call (HuggingFace Datasets, Anthropic, Voyage, Cohere, Braintrust, Motley Fool's public transcript pages). We trust their TLS but assume nothing about their internal handling.
- Transcript text from public sources. We treat the content as untrusted input, not as authoritative.

## Threat model — OWASP LLM Top 10 (2025) mapping

| ID | Risk | Applies | Mitigation |
|---|---|---|---|
| LLM01 | Prompt injection | Yes | Strip instruction-like phrases from every retrieved chunk before it reaches a synthesis prompt. The realistic vector is a hostile speaker planting strings like "ignore previous instructions" inside an analyst question. |
| LLM02 | Sensitive info disclosure | Yes | Output filter on every response. The corpus is public earnings content, so PII risk is low; the real concern is leaking system prompts or internal IDs. |
| LLM03 | Supply chain | Yes | Pin every dependency in `pyproject.toml`. Use `uv lock` for reproducible installs. Review `uv tree` before adding new packages. |
| LLM04 | Data and model poisoning | Yes | Only ingest from a configured allowlist of sources (HuggingFace `jlh-ibm/earnings_call`, Motley Fool transcript pages). Every ingest writes a row to an audit log (source, URL, timestamp, content hash). |
| LLM05 | Improper output handling | Limited | There is no text-to-SQL path in this project. The synthesis output is rendered as markdown in the UI; we escape HTML in the rendering layer. |
| LLM06 | Excessive agency | Limited | The agent has read-only DB access and HTTP-out for embedding, rerank, and Claude APIs. No write tools, no shell, no email. |
| LLM07 | System prompt leakage | Yes | Credentials never go in system prompts. System prompts may be considered exfiltratable; we treat them as such. |
| LLM08 | Vector and embedding weaknesses | Yes | The central RAG risk. Indirect injection via poisoned chunks is mitigated at retrieval time. Embeddings are stored alongside source text and hash, so we can detect tampering. |
| LLM09 | Misinformation | Yes | Every factual claim in an answer requires a citation in the format `[TICKER QQ YYYY, Speaker Name]`. The eval set includes "answer-must-cite" checks. The UI surfaces sources prominently so users can verify. |
| LLM10 | Unbounded consumption | Yes | Per-query token cap (8K input, 2K output), per-session cost ceiling ($3.00), aggregate hourly circuit breaker ($5), Haiku→Sonnet→Opus cascade. All centralized in `src/guardrails.py`. |

## Defense-in-depth layers

No single guardrail is enough. Four layers stack:

1. **Input.** Reject prompts over the token cap. Pattern-filter obviously hostile inputs (long sequences of role-switching tokens, base64 blobs, etc.). An LLM classifier picks up the cleverer ones.
2. **Retrieval.** Every chunk gets normalized: strip "ignore previous instructions" and similar patterns, strip role-switching markers (`system:`, `assistant:`), cap chunk size before it reaches the synthesis context. Every retrieval is logged with `chunk_id` and `query_hash` for audit.
3. **Output.** Schema-validate any structured output (the citations array, the topics array). Reject responses that lack citations on factual claims. PII filter runs on free-form text (the corpus is public earnings content, so this is belt-and-suspenders).
4. **Telemetry and budget.** Braintrust logs every LLM call with tokens, cost, and latency. The cost circuit breaker reads from the same store. When it trips, the system returns a maintenance message.

## Cost guardrails (LLM10 in detail)

Cost is a security concern, not just a finance one. Four patterns:

1. **Per-query caps.** Hard limit on tokens in and out. Reject and explain.
2. **Per-session ceiling.** Track cost by session ID (authenticated) or IP (public demo). Soft block at $0.50 with a clear message.
3. **Aggregate circuit breaker.** If hourly total exceeds $5, the system returns a maintenance message until manual review.
4. **Model cascade.** Haiku → Sonnet → Opus, escalating only when the cheaper model fails validation. Cuts 5–10x cost on typical queries.

LLM enrichment (the one-shot Sonnet call per chunk to extract `hedging_score`, `sentiment`, `topics`) is amortized cost. We pay tokens once at ingest so query-time retrieval can filter on those signals without rerunning the LLM.

## How to report a vulnerability

Email: `isaiah.e.malone@gmail.com` with the subject line `[security] Earnings Call RAG`. Include reproduction steps and the commit hash you tested against. I'll acknowledge within 72 hours. Please don't open a public GitHub issue for security reports — use email or a private vulnerability advisory on this repo.

## Public-corpus disclosure

Everything ingested by this project is public content (HuggingFace `jlh-ibm/earnings_call`, Motley Fool transcripts) covering the Mag 7's quarterly earnings calls from Q2 2024 through Q1 2026. The corpus contains no personal information beyond what executives, analysts, and operators say on the public record during these scheduled calls. Material non-public information is, by SEC rule, not in the transcripts.
