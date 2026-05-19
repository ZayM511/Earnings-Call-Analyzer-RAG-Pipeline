# Interview Talking Points

Living document. Seeded with the v3.5 talking points from the RAG Build Guide. Add to it as the project develops — every design decision, every alternative rejected, every metric measured.

By the time the project is ready to show, this skill is a complete interview-prep file.

## How to use this file

When prepping for an interview, scan top-to-bottom. Read the verbatim answers a couple of times so they sound natural rather than memorized. Pick the analogies that fit your speaking style.

When building, **add** to this file:

- A decision you made (what you picked, what you rejected, why)
- A metric you measured (recall@5 before and after a change, latency at p50 and p95)
- A bug that taught you something (what broke, what you changed, what the eval set caught)

## v3.5 seed answers

### When asked about MCP / Plugins / Skills experience

"I've shipped three production apps — JobFiltr, Rentvolt, and ConsentLens — that each combined multiple MCP servers, Plugins, and Skills to deliver their core functionality. That's where most of my hands-on integration experience comes from: deciding which MCP servers to wire in for which capabilities, handling the trade-offs around auth, rate limits, error surfaces, and plugin compatibility, and knowing when to consume an existing MCP server versus build a custom one. For this RAG project, my `.claude/mcp/` folder documents the servers I wired in (Playwright for browser tasks, Jam for bug capture, Filesystem and GitHub for repo and file access, Postgres for direct DB inspection, shadcn for UI installs) and why each one belongs."

### When asked about internal-document RAG (the LLNL-style question)

"I built two public RAG projects to prove the pipeline, and templates that show how I would adapt the same shape to an internal-document domain. I deliberately did not build a fake internal-document demo on simulated data, for two reasons. First, using a real organization's internal documents without explicit approval would violate data handling policy, and proves nothing other than poor judgment about data boundaries. Second, a synthetic version would not test the real challenge: ACL enforcement, real document format diversity, real versioning, real freshness pressure. The adaptation surface for internal-document RAG is well-defined: source ingestion, ACL metadata column with GIN-indexed `allowed_groups`, format-specific parsers, versioning and freshness handling. I would want to do that work inside your security boundary with your data and your stakeholders, not simulate it externally."

### When asked about closed-loop / on-prem deployments

"I know when to reach for self-hosted narrow models versus API-based ones. The decision tree is operational: can you send data to external APIs, is p99 latency under 100ms required, are you processing more than 10M items a month, does any specific task have a fine-tuned narrow model that beats general LLMs on your eval set. For a deployment with internal data and an enterprise Claude account, I would use the enterprise APIs where allowed and self-hosted models from HuggingFace where the data classification requires it. The architecture stays the same; the model layer is the configurable piece. Same applies to embedding: voyage-3-large for general, voyage-finance-2 or domain-tuned for specialized, self-hosted bge-large or nomic-embed-text for fully on-prem."

### When asked about reducing LLM token usage and costs

"Three patterns, all baked into my projects: per-query token caps to prevent attacks or accidents that drain budget, per-session cost ceilings to bound any single user, and a model cascade that tries Haiku first, escalates to Sonnet on failure, and only reaches Opus for the genuinely hard synthesis. There is also LLM enrichment as one-time amortized cost: for this earnings project I pay tokens once at ingest to extract hedging scores, sentiment, and topic tags, and queries forever get those signals without additional LLM cost. Plus aggregate circuit breakers at the project level so that one bad day cannot run away with the budget."

### When asked about guardrails and safety

"I followed the OWASP LLM Top 10 (2025) as my framework. The biggest RAG-specific risk is LLM08, vector and embedding weaknesses, things like embedding inversion and indirect prompt injection through retrieved content. My pipeline treats every retrieved chunk as untrusted data and strips instruction-like phrases before they hit the synthesis prompt. I also enforce LLM10 with the token caps and cost cascade I just mentioned. Guardrails live in three places by design: CLAUDE.md for always-on rules Claude Code reads every session, SECURITY.md as a public policy GitHub recognizes specially, and a Security section in the README that links to both."

### When asked about your repo structure (the architect question)

"My `.claude/` directory has five kinds of artifacts. Agents are specialists I delegate to. Commands are workflows I invoke. Hooks are guardrails that always run. Skills are the knowledge layer they all read from. MCP servers are the integration layer that connects Claude Code to external systems. The separation maps to how production AI teams structure their tooling: act, invoke, enforce, know, integrate. The whole thing is documented and self-explanatory if someone clones the repo."

### When asked about your evaluation methodology

"I treat evals like tests. I maintain a 30-question dataset in Braintrust, stratified across the query types my system actually serves — single-call deep-dive, multi-quarter trend, and cross-company comparison. After every meaningful pipeline change, I run the full eval set and compare to the previous baseline. The README has screenshots of three experiments that mattered: voyage-3-large vs voyage-finance-2, with reranker vs without, and with hedging-score metadata pre-filter vs without. Anyone can ship a working pipeline; measuring whether it stays working is what separates a demo from production work."

### When asked why earnings calls (and not, say, 10-Ks)

"Earnings calls are weird in a way that's interesting for RAG. Execs read prepared remarks like they're delivering a wedding speech, and then analysts pepper them with questions and you watch them squirm. The prepared section is polished talking points; the Q&A is improvised and full of hedging language when guidance gets uncertain. I built a system that respects that structure — chunks at speaker boundaries, classifies role, tags each chunk with a hedging score — so queries like 'where did execs start hedging on forward guidance' become a one-line metadata filter. 10-Ks are flat by comparison. Calls have voice."

## Simplified analogies

Pick the ones that feel natural and rotate them in when explaining to non-ML stakeholders.

- **Embeddings.** "Picture every chunk of text as a dot on a map. Texts about similar things end up near each other. Embeddings are how I draw the map. Search becomes: which dots are closest to my question?"
- **Hybrid retrieval.** "BM25 is a librarian who matches the exact words on your card. Vector search is a librarian who knows what the book is about. The reranker is the senior librarian who sees both lists and tells you which books actually answer your question."
- **Reranker.** "Cheap retrieval is a wide net — pulls in 50 candidates. The reranker is the slow, smart pass that re-sorts those 50. Two-stage retrieval is how you get both speed and accuracy."
- **Metadata filtering.** "You don't search every book in the library for a Q3 Apple quote. You walk to the Apple shelf first, then to the 2024 row, then to the Q3 spot. Metadata filtering is that walk."
- **LLM enrichment.** "Pre-cooking. Instead of asking Claude to score hedging every time someone queries, I scored every chunk once at ingest time. Query-time stays fast because the hard thinking already happened."
- **Speaker-aware chunking.** "The transcript already tells me where one person stopped talking and another started. Why throw that away with a fixed-character chunker? I chunk at speaker turns because that's where meaning actually breaks."
- **Why Postgres + pgvector.** "I wanted my SQL and my vectors in the same place, in the same query, in the same transaction. Splitting them across two systems is a tax I didn't want to pay."
- **Braintrust.** "Tests, but for AI. Software engineers write unit tests. AI engineers write eval sets. Braintrust is what makes the eval set run automatically, track regressions, and let me compare experiments side by side."

## The 60-second pitch for this project

"Earnings calls are weird — execs read prepared remarks like they're delivering a wedding speech, then analysts pepper them with questions and you watch them squirm. I built a system that ingests quarterly calls across the Mag 7 from Q2 2024 to Q1 2026, splits transcripts the way humans actually consume them (by speaker, not by character count), and lets you ask things like 'show me where Apple's CFO started hedging on guidance' or 'compare how Apple and Google describe China risk.' Postgres with pgvector handles hybrid search, Voyage's finance-tuned embeddings, Cohere reranks, Claude synthesizes the answer with inline citations. Braintrust tracks the evals."

## My design decisions log (add as I build)

| Decision | What I picked | What I rejected | Why |
|---|---|---|---|
| Database | Postgres + pgvector | SQLite + sqlite-vec; separate vector DB | One transaction, one connection pool, hybrid query in one SQL statement |
| Embedding model | voyage-finance-2 | voyage-3-large (the general baseline) | Finance-tuned outperforms general on earnings-call terminology — capture the delta in Braintrust |
| Chunking | Speaker-aware, 200-token floor, 600-token ceiling | Recursive 400-token (the tutorial default) | Earnings calls have free structural signal in the speaker headers; fixed-char chunking destroys it |
| Synthesis model | Claude Opus 4.6 | Sonnet 4.5 for cost | Synthesis is the one place where Opus's longer-form reasoning lands the citations correctly |
| Enrichment model | Claude Sonnet 4.5 | Haiku 4.5 | Haiku undercounts hedging on subtle phrases; Sonnet's calibration is closer to human raters |
| Contextual retrieval prefix | Yes | Skip | One-time embed-cost increase; 35-50% recall lift per Anthropic 2024 |
| (add more as you build) | | | |

## Metrics I've measured (add as I build)

| Change | Metric | Before | After | Notes |
|---|---|---|---|---|
| Contextual retrieval prefix | recall@5 | TBD | TBD | Expect 35-50% improvement per Anthropic 2024 |
| voyage-finance-2 vs voyage-3-large | recall@5 | TBD | TBD | Expect 5-15% improvement on finance terminology queries |
| With Cohere rerank vs without | recall@5 | TBD | TBD | Expect 15-25% improvement |
| (add more as you build) | | | | |

## Bugs that taught me something (add as I build)

(Write a short story for each meaningful bug. What broke, what you changed, what the eval set caught. These are the most memorable interview material.)
