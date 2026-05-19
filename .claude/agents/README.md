# .claude/agents/

Specialized subagents. Each agent has its own context window and its own system prompt. Claude Code delegates a task to an agent by name (or auto-routes when the task matches).

## What's here

| Agent | When it runs |
|---|---|
| `tdd-engineer` | Before any new module or non-trivial function. Writes a failing test, watches it fail, then implements the minimum code to pass. |
| `rag-eval-reviewer` | Whenever new eval cases are added. Flags weak cases, suggests harder variants, checks the single-call / multi-quarter / cross-company stratification. |
| `security-reviewer` | Before any deploy or push to `main`. Scans for hardcoded secrets, missing env-var validation, OWASP LLM Top 10 violations. |

The NBA sibling project also ships a `sql-reviewer` agent. This project doesn't, because there is no text-to-SQL path — retrieval is hybrid BM25 + dense vector + Cohere rerank, and there's nothing to gate.

## Why agents and not just one big assistant

Each agent has a narrow focus and a clean context window. The `security-reviewer` doesn't need to know about chunking strategy; the `tdd-engineer` doesn't need to know about the OWASP threat model. Narrow context produces narrower, more reliable judgments.

## Invocation rules

- **`tdd-engineer`:** invoke before writing the implementation, not after. "Add a function that classifies a speaker's role from the transcript header" → spawn tdd-engineer first.
- **`rag-eval-reviewer`:** spawn whenever the eval set under `src/eval/` grows or changes. Even adding a single case triggers a review.
- **`security-reviewer`:** spawn before `git push origin main` or any deploy. Also spawn after touching anything that handles credentials or untrusted input (every chunk is untrusted; the scraping code is the highest-risk surface).
