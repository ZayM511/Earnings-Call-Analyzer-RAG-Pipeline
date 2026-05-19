# Earnings Transcript Parsing

Speaker turn detection, role classification, and prepared/qa section detection are the core domain primitives of this project. Get them right and the entire downstream pipeline (chunking, retrieval, citations) inherits the structure.

This skill explains the approach. The implementation lives in `src/chunk/speaker_aware_chunker.py`.

## The problem

Earnings call transcripts come from different sources with different header conventions:

- **Motley Fool** (`fool.com/earnings/call-transcripts/...`):
  ```
  Tim Cook -- CEO
  Thanks, Suhasini, and good afternoon, everyone. We delivered our best
  September quarter ever, with revenue of $94.9 billion...
  ```
- **HuggingFace `jlh-ibm/earnings_call`** (varies by year; usually `Speaker Name:` on its own line):
  ```
  Tim Cook:
  Thanks, Suhasini. We delivered our best September quarter ever...
  ```
- **Seeking Alpha** (when scraped):
  ```
  Tim Cook
  Chief Executive Officer
  Thanks, Suhasini...
  ```
- **FMP API** (returns JSON with speaker name and role as separate fields).

The parser dispatches on source format and emits a uniform list of speaker turns regardless.

## The approach

### Stage 1 — Tokenize into speaker turns

For each source, a regex identifies speaker headers and splits the body text by them. The base regex (Motley Fool style):

```python
# Matches "Tim Cook -- CEO" on a line by itself.
HEADER_RE = re.compile(
    r"^(?P<name>[A-Z][\w'\.\-]+(?:\s+[A-Z][\w'\.\-]+)*)"
    r"(?:\s+--\s+(?P<role>[A-Za-z &\-\/]+))?$",
    re.MULTILINE,
)
```

Per-source variants live in `src/chunk/parsers/*.py`. Each returns the same `SpeakerTurn` dataclass:

```python
@dataclass(frozen=True)
class SpeakerTurn:
    speaker_name: str
    role_hint: str | None      # what the header said (e.g., "Chief Financial Officer")
    text: str
    position: int              # 0-indexed within the call
```

### Stage 2 — Classify roles

Map `role_hint` to a canonical role label:

| `role_hint` contains | Canonical role |
|---|---|
| `CEO`, `Chief Executive` | `CEO` |
| `CFO`, `Chief Financial` | `CFO` |
| `Analyst`, an analyst's firm name | `Analyst` |
| `Operator` | `Operator` |
| anything else, or `None` | `Other` (fall back to a per-ticker exec lookup) |

The per-ticker exec lookup is a small dict keyed on `(ticker, year_quarter)` that maps a speaker's last name to their role at the time. It's needed because:

- Pichai joined Alphabet's board in 2024 with a new title format
- META's CFO changed multiple times during the 8-quarter window
- TSLA's "Vaibhav Taneja" wasn't always the CFO

The lookup lives in `data/exec_lookup.json` and is small enough to maintain by hand. Add a row when the heuristic guesses wrong.

### Stage 3 — Detect the prepared / qa transition

Earnings calls have a stable structure:

1. **Prepared remarks** — CEO opens, CFO walks through the financials, sometimes a strategy update.
2. **Operator's transition** — a stock phrase along the lines of `"we will now begin the question-and-answer session"` or `"Operator, we're ready for questions"`.
3. **Q&A** — analysts ask, execs answer, until the operator wraps up.

Detection rule: walk the turns in order. Start with `section = 'prepared'`. Flip to `section = 'qa'` after detecting either:

- An Operator turn containing `"begin the question-and-answer"` (case-insensitive)
- An Operator turn containing `"first question"` or `"open the line"`
- An Analyst turn (analyst presence after an Operator turn implies Q&A has started)

If no transition is detected (rare but happens for short calls), default to `section = 'qa'` for the back half of turns. Better to mis-label one boundary than to miss the structure entirely.

### Stage 4 — Merge tiny turns up to a 200-token floor

A one-line Operator turn like `"Thank you. Our next question is from..."` has no semantic value alone. The merger folds adjacent short turns into the surrounding context:

```
Turn A (Operator, 18 tokens): "Thank you. Our next question is from Wamsi Mohan of Bank of America."
Turn B (Analyst, 90 tokens):  "Tim, on the AI side, I wanted to understand..."
Turn C (CEO Tim Cook, 240 tokens): "Wamsi, thanks for the question. We're really excited about..."

After merge:
Chunk 1 (section='qa', speaker_role='CEO', ...300 tokens combining A+B+C up to floor)
```

The merge respects role precedence: when folding, the dominant turn (the longest, usually the exec answer) keeps its `speaker_name` and `speaker_role`. The Operator and Analyst lines become preamble inside the chunk's `text`.

### Stage 5 — Split long turns at sentence boundaries (600-token ceiling)

CFOs occasionally deliver 900-token monologues during prepared remarks. Splitting at sentence boundaries preserves coherence:

```python
import re

SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

def split_long_turn(turn: SpeakerTurn, ceiling: int = 600) -> list[SpeakerTurn]:
    sentences = SENT_RE.split(turn.text)
    chunks, current, current_tokens = [], [], 0
    for sentence in sentences:
        sent_tokens = approx_tokens(sentence)
        if current_tokens + sent_tokens > ceiling and current:
            chunks.append(SpeakerTurn(..., text=" ".join(current)))
            current, current_tokens = [], 0
        current.append(sentence)
        current_tokens += sent_tokens
    if current:
        chunks.append(SpeakerTurn(..., text=" ".join(current)))
    return chunks
```

All sub-chunks inherit the original turn's `speaker_name`, `speaker_role`, and `section`.

## Concrete example

Raw transcript excerpt:

```
Tim Cook -- CEO
Thanks, Suhasini, and good afternoon, everyone. We delivered our best
September quarter ever, with revenue of $94.9 billion, up 6% year over year.

Luca Maestri -- CFO
Thank you, Tim. Our financial performance in the quarter was driven by...
[600 more tokens]

Operator
Thank you. Our first question comes from Erik Woodring of Morgan Stanley.

Erik Woodring -- Morgan Stanley -- Analyst
Tim, on Apple Intelligence — when do you expect to see a meaningful revenue
inflection from this?

Tim Cook -- CEO
Erik, we're seeing strong customer engagement with Apple Intelligence features...
```

Parser output (after merge + split):

```
[
  {speaker_name: "Tim Cook",     role: "CEO",      section: "prepared",
   text: "Thanks, Suhasini, and good afternoon...", chunk_index: 0},
  {speaker_name: "Luca Maestri", role: "CFO",      section: "prepared",
   text: "Thank you, Tim. Our financial performance...", chunk_index: 1},
  {speaker_name: "Luca Maestri", role: "CFO",      section: "prepared",
   text: "...continued from the previous chunk", chunk_index: 2},
  {speaker_name: "Tim Cook",     role: "CEO",      section: "qa",
   text: "Operator: ... Erik Woodring: Tim, on Apple Intelligence... Tim Cook: Erik, we're seeing strong customer engagement...",
   chunk_index: 3},
  ...
]
```

The Operator and Analyst lines were folded into Tim Cook's answer (merge up to 200-token floor); the CFO's long monologue was split into two 500-ish-token sub-chunks at a sentence boundary.

## Edge cases worth coding tests for

- **No header for an opening Operator line.** Some transcripts start mid-sentence with the Operator already speaking. Default to `speaker_role = 'Operator'` if the first turn has no name.
- **Analyst follow-up questions in the same paragraph as the exec's answer.** Detect with a follow-up regex like `r"\b[A-Z][a-z]+ [A-Z][a-z]+\b\?$"` at the end of a sentence; if a name-like string ends the previous sentence in question form, it's the analyst handing off.
- **Hyphenated names.** "Anders Bylund -- The Motley Fool" — the firm name after `--` shouldn't be misread as a role. Filter against a known role allowlist.
- **Possessives in headers.** "Tim Cook's Q3 commentary" — never a real header; reject if it ends in `'s`.
- **Bilingual or transliterated names.** Most Mag 7 execs use English names in their calls; unlikely to need normalization here.
- **Embedded SEC disclaimers.** Some transcripts include a "Forward-Looking Statements" block before the first speaker turn. Strip it before parsing.
- **All-caps speaker headers.** Some sources use `TIM COOK -- CEO`. Normalize to title case before the regex matches.

## Refresh cadence

- Initial parsing at ingest time.
- One-shot re-parse if the per-ticker exec lookup gains a new mapping.
- No live refresh — earnings calls are immutable historical artifacts. Once parsed, the chunks don't change.

## Why this matters for the project pitch

In interviews, this is the answer to "how did you adapt RAG to a specialized corpus?"

The two-sentence version: *"Earnings calls have natural structure: prepared remarks then live Q&A, with named speakers in known roles. I built a speaker-aware chunker that respects that structure, so a query about CFO guidance can filter to CFOs in prepared remarks instead of scanning the whole transcript. Tutorial-default chunking destroys the structure that makes the corpus interesting."*
