# Dispatching Parallel Agents

When you have three or more independent problems, dispatch focused subagents in parallel instead of solving them serially. Parallel dispatch is one of the largest productivity multipliers in agent-driven development.

This skill explains when to fan out and how, with five RAG-specific use cases.

## The rule

**Three independent tasks = parallel. Two = decide case-by-case. One = direct work.**

"Independent" means the tasks don't share state and don't need each other's output. Three eval failures across different query types are independent. Three steps in one ingestion pipeline are not.

## How to dispatch

Use a single message with multiple `Agent` tool calls. Claude Code executes them concurrently and returns when each finishes.

```
I'll run three diagnostics in parallel:
- agent A on single-call failures
- agent B on multi-quarter failures
- agent C on cross-company failures
```

Then make three `Agent` calls in one turn. Wait for results. Synthesize.

Each agent gets:

- A short, self-contained prompt (the agent has no conversation context).
- A specific deliverable ("report findings in under 200 words").
- Any file paths or context it needs to do the work.

## RAG-specific use cases

### 1. Re-embedding multiple corpora after an embedding-model change

If you upgrade from `voyage-3-large` to `voyage-finance-2`, every chunk needs re-embedding. Split by ticker; dispatch a worker per ticker.

```
- Agent A: re-embed chunks where ticker IN ('AAPL', 'MSFT', 'GOOGL')
- Agent B: re-embed chunks where ticker IN ('AMZN', 'META')
- Agent C: re-embed chunks where ticker IN ('NVDA', 'TSLA')
```

Each worker reports tokens consumed, time elapsed, error count.

### 2. Fixing stratified eval failures

After running the eval set, you get failures distributed across single_call / multi_quarter / cross_company. Each type has different root causes (wrong retrieval, wrong synthesis prompt, wrong contextual prefix). Dispatch one agent per query type.

```
- Agent A: triage single_call failures, propose fixes for retrieval filters
- Agent B: triage multi_quarter failures, propose fixes for the temporal ordering of citations
- Agent C: triage cross_company failures, propose fixes for the synthesis prompt's comparison framing
```

Each returns a short list of "this is the bug" + "this is the fix" entries.

### 3. Testing parallel chunking experiments

When deciding between speaker-aware-200-floor / speaker-aware-300-floor / recursive-400-token, run them in parallel.

```
- Agent A: ingest a 5-call sample with strategy 1, run the eval set, report recall@5
- Agent B: same with strategy 2
- Agent C: same with strategy 3 (the recursive baseline)
```

Then compare the three reports.

### 4. Researching multiple library choices

Picking between three reranker providers (Cohere, Voyage, Jina) — dispatch one researcher per option to gather pricing, latency, recall numbers, integration shape. Each returns a one-page summary.

```
- Agent A: investigate Cohere Rerank 3.5 — pricing, latency p50/p95, recall on a public benchmark, integration code shape
- Agent B: same for Voyage rerank-2
- Agent C: same for Jina reranker-v2
```

### 5. Parallel transcript ingestion across sources

Pulling transcripts from HuggingFace, Motley Fool, and (if escalated) FMP involves different rate limits, formats, and error modes. Dispatch one ingest agent per source.

```
- Agent A: pull all Mag 7 Q2 2024 – Q1 2026 transcripts from HF (datasets.load_dataset)
- Agent B: scrape any missing quarters from Motley Fool
- Agent C: (only if A+B leave gaps) fetch from FMP API
```

Each agent writes to a per-source staging directory; the orchestrator merges them and writes `data/raw/{ticker}_{year}{quarter}.json`.

## When NOT to fan out

- **Sequential dependencies.** Step 2 needs step 1's output → run them in order.
- **Shared mutable state.** Multiple agents writing to the same table without coordination → races.
- **Two tasks.** The overhead of fanning out and synthesizing isn't worth it for two. Just do them yourself.
- **The user is waiting for one answer.** Fanning out is invisible to the user; sometimes the right move is to spend 30 seconds doing the thing.

## How to phrase the synthesis

After agents return, write a synthesis the user can read. Don't dump three full reports back; condense.

```
Three runs are in:

- Strategy 1 (speaker-aware, 200-token floor): recall@5 = 0.81
- Strategy 2 (speaker-aware, 300-token floor): recall@5 = 0.78
- Strategy 3 (recursive 400-token, the tutorial baseline): recall@5 = 0.66

Recommendation: ship strategy 1 as the default. The 200-token floor beats 300
because tiny Operator/Analyst turns get folded in, preserving question-and-answer
pairing. The recursive baseline confirms the speaker-aware choice was worth the work.
```

## Anti-patterns

- **Fanning out three agents that all read the same file.** The overhead is wasted; one agent reading the file once is faster.
- **Returning all three reports verbatim.** Synthesize. The user delegated to you.
- **Forgetting to brief each agent.** Each agent starts fresh; it has no idea what the conversation is about. The prompt must be self-contained.
- **Parallelizing destructive operations without checking for conflicts.** Three agents all migrating the same table = corruption.
