# Chunking Strategies — 2026 Reference

Consult this skill before writing any chunking code. Chunking is one of the highest-leverage decisions in a RAG pipeline; the wrong choice cannot be saved by better embeddings or rerankers.

## The 2026 cheat sheet

| Document type | Recommended strategy | Why |
|---|---|---|
| Generic prose (news, articles, Reddit) | Recursive, 400-512 tokens, 10-20% overlap | The 2026 default. Best balance of precision and context. |
| Multi-topic prose with clear sections | Semantic chunking with a 200-token minimum floor | Semantic alone produces tiny fragments (43-token average); the floor fixes it. |
| **Structured documents (10-Ks, earnings calls)** | **Structure-aware (by section / speaker turn)** | **The structure is a free signal; ignoring it is wasteful.** |
| Code | AST-based (tree-sitter) | Function and class boundaries are the natural unit. |
| Short focused docs (FAQs, tickets) | No chunking, embed the whole doc | Chunking small docs hurts retrieval more than it helps. |
| Tables and numeric data | Don't embed — query SQL instead (route) | Vector search is the wrong tool for numeric questions. |

## What this project does

**Earnings call transcripts: structure-aware on speaker turns, 300-600 tokens per chunk, 200-token floor, 600-token ceiling.**

Earnings calls have natural structure: prepared remarks by CEO and CFO, then live Q&A between analysts and execs. Chunking at speaker boundaries preserves the structural reality (a CFO's hedged answer behaves differently from a CEO's prepared talking point). Slicing mid-sentence destroys meaning; slicing mid-speaker-turn destroys coherence.

The chunker's contract:

1. Parse the transcript into speaker turns using regex on speaker headers (e.g., `^([A-Z][a-z]+ [A-Z][a-z]+(?: -- [A-Z]+)?):` for the `Tim Cook -- CEO:` style). Each source format (Motley Fool, HuggingFace, FMP) has its own header style; the parser dispatches by source.
2. Detect the prepared/qa transition. The Operator's "we'll now begin the Q&A" line flips the section flag.
3. Classify each speaker's role (CEO, CFO, Analyst, Operator, Other) using the header role hint when present, otherwise a small lookup table of known execs per ticker.
4. Merge tiny adjacent turns up to a 200-token floor. A one-sentence Operator turn folds into the surrounding turn.
5. Split long monologues (mostly CFOs) at sentence boundaries to a 600-token ceiling.

Output: a list of chunks each carrying `ticker`, `company`, `quarter`, `year`, `call_date`, `speaker_name`, `speaker_role`, `section`, `chunk_index`, `text`.

**Anti-pattern for this corpus: fixed-character chunking.** It shreds the speaker structure that makes the calls interesting. Every tutorial defaults to this; rejecting it is the move that separates a portfolio project from a tutorial follow-along.

## Layered upgrades

Once the base strategy is in place, three upgrades give big wins for low effort. Worth knowing both for the project and for interviews.

### Contextual retrieval (Anthropic, 2024)

Before embedding each chunk, prepend a short context line. Format used in this project:

```
From {company}'s {quarter} {year} earnings call, {speaker_name} ({role}) in {section}: {chunk_text}
```

Concrete example:

```
From Apple's Q3 2024 earnings call, Tim Cook (CEO) in qa:
We continue to be very excited about Apple Intelligence. As Luca mentioned,
we'll be rolling it out gradually across our installed base over the coming
quarters, and we feel great about the customer response so far...
```

Expect a 35–50% recall lift on hard queries. One-time embedding cost; permanent benefit. Pay attention to this on the eval set — it's often the single largest accuracy improvement available.

**Apply the prefix at embed time only.** The stored `text` column keeps the raw chunk text — citations and the UI display use the raw text, not the prefix.

### LLM enrichment (this project's specific upgrade)

In addition to the contextual prefix, every chunk gets enriched once at ingest with Claude Sonnet 4.5:

- `hedging_score`: 0.0–1.0, how much qualifying language the speaker uses
- `sentiment`: positive | neutral | negative
- `topics`: up to 5 short labels (e.g., `["AI capex", "China risk", "Q4 guidance"]`)

These metadata columns turn impossible-at-query-time questions into one-line filters: "Show me the most evasive exec answers about AI capex in Q3 2024" becomes `WHERE topics @> ARRAY['AI capex'] AND year = 2024 AND quarter = 'Q3' AND hedging_score >= 0.7 ORDER BY hedging_score DESC`.

Amortized cost. The hedging score would be impossible to compute at query time without huge latency hits.

### Parent-child / small-to-large

Embed small chunks (precise retrieval) but return the surrounding larger chunk (better context for synthesis). 10-15% accuracy gain.

For this project, the "parent" could be the full speaker turn (which might span several 600-token chunks if the CFO went long) and the "child" the 300-600-token sub-chunk. Worth adding once the base pipeline is shipping.

### Rich metadata on every chunk

Metadata pre-filtering is the cheapest accuracy gain in RAG. Every chunk in `chunks` carries:

- `ticker VARCHAR(10)` — GIN-indexed via `chunks_ticker_idx`. Pin to a specific company.
- `quarter VARCHAR(4)`, `year INT` — composite index. Pin to a specific call.
- `speaker_role VARCHAR(20)` — filter to CEO-only or analyst-only views.
- `section VARCHAR(20)` — `prepared` vs `qa`.
- `hedging_score REAL`, `sentiment VARCHAR(20)`, `topics TEXT[]` — Claude-extracted signals; the `topics` column is GIN-indexed for array containment.

Filtering on `ticker = 'AAPL' AND year = 2024 AND quarter = 'Q3'` turns a 6000-chunk vector search into a ~70-chunk vector search. That's a meaningful accuracy lift because irrelevant chunks can't sneak into the top-K.

## Decision tree (in code form)

```
def pick_strategy(doc):
    if doc.kind == "stats_table":
        return "do not embed, route to SQL"
    if doc.kind == "code":
        return "AST-based (tree-sitter)"
    if doc.kind == "earnings_call" or doc.kind == "transcript_with_speakers":
        return "structure-aware on speaker turns, 200-token floor, 600-token ceiling"
    if doc.token_count < 200:
        return "embed whole doc, no chunking"
    if doc.has_explicit_sections and doc.token_count > 2000:
        return "semantic with 200-token floor"
    # default: generic prose
    return "recursive 400 tokens, 15% overlap, contextual retrieval prepended"
```

## Anti-patterns

- **Fixed-character chunking on transcripts.** Splits mid-speaker, mid-sentence, mid-word; loses meaning. Use speaker-aware splitting that respects the structure.
- **Treating the prepared section and Q&A as the same kind of text.** They aren't. A CEO's prepared remark is a polished talking point; a CFO's Q&A answer is improvised. The `section` metadata captures the difference.
- **Skipping the role classifier.** Without `speaker_role`, you can't ask "show me only what the CFO said about guidance." That's half the demo's power.
- **Embedding tables as text.** Numbers in prose form lose their relational structure. Earnings calls embed financial figures inside English sentences ("we delivered $94 billion in revenue, up 12% year over year"); that's fine for retrieval but you wouldn't want to use vector search to *compute* revenue.
- **Skipping the contextual-retrieval prefix.** It's a free 35–50% recall lift. The only reason not to do it is laziness.

## Research links

- Anthropic, "Contextual Retrieval," 2024.
- Jina AI, "Late Chunking in Long-Context Embedding Models," 2024.
- LlamaIndex, "Parent-Child Document Retriever" pattern.
- Pinecone, "Chunking Strategies for LLM Applications," 2024 — useful for the recursive-vs-semantic comparison numbers.

## Interview angle

"Naive fixed-size chunking destroys earnings call semantics. I chunk on speaker boundaries because each speaker turn is a coherent unit of meaning. A CFO's prepared remarks behave differently from a live Q&A response — chunking captures that structural reality. Layered contextual retrieval on top, prepending a short context note to each chunk before embedding, which gave me a recall@5 lift on my eval set. The tutorial-default fixed-character chunker would have shredded the semantic structure."
