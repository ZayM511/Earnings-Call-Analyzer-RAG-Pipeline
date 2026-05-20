import Link from "next/link";
import { Code2, Sparkles, ExternalLink } from "lucide-react";
import { SiteHeader } from "@/components/site-header";
import { PipelineDiagram } from "@/components/pipeline-diagram";

const REPO_URL = "https://github.com/ZayM511/Earnings-Call-Analyzer-RAG-Pipeline";
const REPO_COMMIT = (sha: string) => `${REPO_URL}/commit/${sha}`;
const REPO_BLOB = (path: string) => `${REPO_URL}/blob/main/${path}`;

export const metadata = {
  title: "How I Made This · Earnings Call Analyzer",
  description:
    "The build story behind the Earnings Call Analyzer: a hybrid-retrieval RAG over Mag 7 quarterly earnings call transcripts (Q2 2024 → Q1 2026). Speaker-aware chunking, Voyage finance-tuned embeddings, Cohere rerank, Claude Opus synthesis with inline citations.",
};

export default function HowIMadeThisPage() {
  return (
    <div className="flex flex-col flex-1 min-h-screen bg-(--background)">
      <SiteHeader />

      <main className="mx-auto w-full max-w-[920px] px-6 py-10 flex flex-col gap-8">
        <TitleRow />
        <TLDR />

        <SectionDivider label="Architecture" />
        <PipelineDiagram />

        <SectionDivider label="Design brief" />
        <DesignBrief />

        <SectionDivider label="Build order" />
        <BuildSteps />

        <SectionDivider label="What turned out to be interesting" />
        <InterestingCallouts />

        <SectionDivider label="Tech stack" />
        <TechStack />

        <SectionDivider label="Evaluation" />
        <EvalSummary />

        <SectionDivider label="What's next" />
        <WhatsNext />

        <PageFooter />
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function TitleRow() {
  return (
    <div>
      <h1 className="text-balance text-3xl md:text-4xl font-medium tracking-tight">
        How I Made This
      </h1>
      <p className="mt-3 max-w-2xl text-(--muted-foreground) leading-7">
        A hybrid-retrieval RAG system over the Mag 7&apos;s quarterly earnings
        calls. Built around one observation: earnings transcripts have a clean
        speaker structure that the standard RAG tutorial throws away — and
        executives hedge more during live Q&amp;A than in prepared remarks. The
        whole pipeline is designed around that structural signal.
      </p>
    </div>
  );
}

function TLDR() {
  return (
    <div className="rounded-2xl border border-(--border) bg-(--card)/60 p-5 md:p-6">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-(--accent)">
        <Sparkles className="size-3" />
        TL;DR
      </div>
      <p className="mt-3 leading-7">
        41 earnings call transcripts (Mag 7, Q2 2024 → Q1 2026) ingested from
        HuggingFace, chunked at speaker boundaries (1,097 chunks), enriched
        once with Claude Sonnet 4.5 for a hedging score + sentiment + topic
        tags, embedded with Voyage <code>voyage-finance-2</code>, and indexed
        in Postgres + pgvector with HNSW. Each user question runs through BM25
        + dense in parallel, RRF-merged, Cohere-reranked, then synthesized by
        Claude Opus 4.6 with inline <code>[TICKER QQ YYYY, Speaker]</code>{" "}
        citations. A 30-case Braintrust eval ships in the repo (overall LLM
        judge 0.94, recall@5 1.00).
      </p>
      <p className="mt-3 text-(--muted-foreground) leading-7 text-[14px]">
        Below: the architecture, the design decisions, the order I built
        things in, what turned out to be interesting, and the tech stack
        with rationale per layer.
      </p>
    </div>
  );
}

function DesignBrief() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <BriefCard
        title="Why earnings calls?"
        body="Calls have free structural signal: scripted prepared remarks then live Q&A, with named speakers in known roles. Tutorial-default fixed-character chunking shreds that. Speaker-aware chunking preserves it — and the resulting 'who said this in what mode' metadata powers questions naive RAG can't ask, like 'show me the most evasive CFO answers about guidance in 2024'."
      />
      <BriefCard
        title="Why hybrid + speaker-aware?"
        body="BM25 catches exact financial phrases ('free cash flow', 'gross margin') that a pure dense lane misses on literal spelling. Dense catches semantic intent ('how did Apple describe China risk?') that a pure keyword lane misses on paraphrase. RRF merges both into one ranking. Cohere Rerank 3.5 is the precision pass on top — it earns its keep on hard cross-company queries."
      />
      <BriefCard
        title="Why this stack?"
        body="Postgres + pgvector keeps SQL filters and vector math in one query, one transaction. Voyage finance-2 is domain-tuned for finance terminology. Cohere is the standard for cross-encoder rerank at this latency band. Claude Opus 4.6 lands long-form citations more reliably than smaller models. Braintrust treats evals like tests — every change runs against the same 30 cases."
      />
    </div>
  );
}

function BriefCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-(--border) bg-(--card)/55 p-5">
      <h3 className="text-[15px] font-semibold tracking-tight">{title}</h3>
      <p className="mt-2 text-[13.5px] leading-7 text-(--muted-foreground)">
        {body}
      </p>
    </div>
  );
}

// Build steps — 11 commits matching the 9 phases that landed.
const BUILD_STEPS: BuildStep[] = [
  {
    n: 1,
    title: "Scaffold the full v3.5 tooling layer",
    sha: "1e3ab09",
    label: "phase 0",
    body: `The repo's first commit landed a complete .claude/ tooling layer + .mcp.json + SECURITY.md + Docker Compose with Postgres 16 + pgvector before a single line of pipeline code. The bet: production AI work lives at the intersection of agents, commands, hooks, skills, and MCP servers — and codifying that first is how you compound velocity over the next 10 phases.`,
  },
  {
    n: 2,
    title: "Ingest 41 transcripts from Rogersurf HF dataset",
    sha: "1647e1b",
    label: "phase 1",
    body: `The original plan called for the jlh-ibm/earnings_call HuggingFace dataset, but that stops at 2020 and uses a deprecated dataset-script format the current datasets library refuses to load. Live Motley Fool scraping hit 429s within a handful of requests. I switched to Rogersurf/earnings-call-transcripts (a redistributed parquet of Motley Fool transcripts) which covers our entire Q2 2024 → Q1 2026 window. 41 of 56 target calls landed — gaps documented honestly in the README.`,
    link: REPO_BLOB("src/ingest"),
    linkLabel: "src/ingest/",
  },
  {
    n: 3,
    title: "Speaker-aware chunker — 41 transcripts → 1,097 chunks",
    sha: "974a483",
    label: "phase 2",
    heart: true,
    body: `Auto-detects two transcript formats: Motley Fool style (Name\\n--\\nRole\\nContent) for AAPL/MSFT/GOOGL/AMZN/META/NVDA, and Tesla style (Name:\\nContent). Detects the prepared → Q&A transition via the operator's "begin the question-and-answer" cue or the first analyst tag. Merges short operator/analyst turns into adjacent exec answers (200-token floor) and splits CFO monologues at sentence boundaries (600-token ceiling). Section split came out 62/38 Q&A/prepared — typical for an earnings call.`,
    link: REPO_BLOB("src/chunk"),
    linkLabel: "src/chunk/",
  },
  {
    n: 4,
    title: "Claude Sonnet 4.5 enrichment — hedging, sentiment, topics",
    sha: "1bc8259",
    label: "phase 3",
    body: `One Sonnet 4.5 call per chunk extracting a hedging_score (0–1, calibrated against five reference examples in the system prompt), sentiment (positive/neutral/negative), and 1–5 short topic labels. Async with asyncio.gather + semaphore-bounded concurrency (8 in-flight), one session-id per call file so no single session hits the $0.50 ceiling. 1,097/1,097 enriched, 7.5 min wall-clock, ~$3.85 total. Q&A average hedging 0.326 vs prepared 0.199 — execs hedge more during live questions, exactly as the corpus design predicts.`,
    link: REPO_BLOB("src/enrich"),
    linkLabel: "src/enrich/",
  },
  {
    n: 5,
    title: "Voyage finance-tuned embeddings + HNSW index",
    sha: "7c355f1",
    label: "phase 4",
    body: `Voyage voyage-finance-2 (1024-dim, finance-tuned, $0.12/M tokens). Called via REST because the voyageai Python SDK fails to import on Python 3.14. The Anthropic-2024 contextual retrieval prefix ("From Apple's Q4 2024 earnings call, Tim Cook (CEO) in prepared remarks: ...") is applied at embed time only — the stored text column keeps the raw chunk so citations look clean. 1,097 vectors embedded in 9 API calls / ~2 min / ~$0.07.`,
    link: REPO_BLOB("src/embed"),
    linkLabel: "src/embed/",
  },
  {
    n: 6,
    title: "Hybrid retrieval: BM25 + dense + RRF + Cohere",
    sha: "4e4c9d4",
    label: "phase 5",
    body: `Postgres ts_rank over a GIN-indexed tsvector (BM25 lane) in parallel with pgvector's <=> cosine operator (dense lane), each returning top-50 with metadata pre-filters applied. RRF (Cormack 2009, k=60) merges the two id-rankings into one. Cohere rerank-v3.5 is the precision pass — sends the merged 50–100 candidates plus the user question, returns top-K with cross-encoder relevance scores.`,
    link: REPO_BLOB("src/retrieve"),
    linkLabel: "src/retrieve/",
  },
  {
    n: 7,
    title: "Opus 4.6 synthesis with inline citations + ask CLI",
    sha: "419f097",
    label: "phase 6",
    body: `System prompt pins Claude to ground every factual claim in the retrieved chunks and emit citations as [TICKER QQ YYYY, Speaker Name]. Each chunk passes through guardrails.sanitize_retrieved_chunk before injection so an attacker can't plant "ignore previous instructions" in a transcript and hijack synthesis (OWASP LLM01/LLM08). Returns a SynthesisResult with the answer, parsed citations (regex), chunks_used, model, tokens, cost, latency. CLI: \`uv run python -m src.synthesize "<question>" --ticker AAPL ...\``,
    link: REPO_BLOB("src/synthesize"),
    linkLabel: "src/synthesize/",
  },
  {
    n: 8,
    title: "30-case Braintrust eval + 2 A/B ablations",
    sha: "0fcfc74",
    label: "phase 7",
    body: `30 hand-designed eval cases (10 single-call / 10 multi-quarter / 10 cross-company), all anchored to calls that actually exist in the corpus. Scorers: recall@5, MRR, theme coverage (substring), citation count floor, and an LLM-as-judge built on Opus with a groundedness + completeness + clarity rubric mapped to 0–1. Baseline: overall judge 0.94 (single-call 0.99, multi-quarter 0.93, cross-company 0.89). Rerank-on/off and hedging-filter ablations both saturated at recall=1.0 — honest finding: at 1,097 chunks with strong metadata pre-filters, ticker-level recall is at ceiling regardless of rerank.`,
    link: REPO_BLOB("src/eval"),
    linkLabel: "src/eval/",
  },
  {
    n: 9,
    title: "Next.js 15 UI + FastAPI backend",
    sha: "106eabe",
    label: "phase 8",
    body: `FastAPI on port 8001 (port 8000 belongs to the sibling NBA project) wrapping ask + companies + chunks lookup endpoints. Next.js 16 (App Router, React 19, Tailwind v4, Turbopack) with hand-rolled shadcn-style primitives on Radix because shadcn init --yes hung on Windows interactive prompts. Two routes: / (ask one question, see cited answer with hover-card citations) and /compare (one question fanned out to 2–4 ticker columns).`,
    link: REPO_BLOB("ui"),
    linkLabel: "ui/",
  },
  {
    n: 10,
    title: "Branding + live pipeline trace + this page",
    label: "phase 9",
    body: `Personal branding (logo + "By Isaiah M." subtitle in the header), a live RAG pipeline visualization that animates through the 6 stages while every query is in flight, and this How-I-Made-This page itself. The static diagram above is the same component pattern as the live trace — just frozen in the all-stages-complete state.`,
  },
  {
    n: 11,
    title: "Visual polish + final screenshots",
    label: "phase 9.5",
    body: `Refined oklch theme tokens (warmer dark, deeper finance-green accent), Newsreader serif for the citation HoverCard quotes, animated gradient sweep on the landing H1, soft dot-grid background, Framer Motion page transitions + citation-chip hover spring + paragraph-stagger entrance for synthesized answers. Re-captured screenshots via Playwright MCP and dropped them into docs/screenshots/ + the README.`,
  },
];

interface BuildStep {
  n: number;
  title: string;
  sha?: string;
  label: string;
  body: string;
  link?: string;
  linkLabel?: string;
  heart?: boolean;
}

function BuildSteps() {
  return (
    <ol className="space-y-3">
      {BUILD_STEPS.map((step) => (
        <Step key={step.n} {...step} />
      ))}
    </ol>
  );
}

function Step({ n, title, sha, label, body, link, linkLabel, heart }: BuildStep) {
  return (
    <li className="rounded-2xl border border-(--border) bg-(--card)/55 p-5">
      <div className="mb-2 flex flex-wrap items-baseline gap-2">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-(--border) bg-(--muted) font-mono text-[11px] tabular-nums">
          {n}
        </span>
        <h3 className="text-[15px] font-semibold text-(--foreground)">{title}</h3>
        <span className="rounded-md border border-(--border) bg-(--muted)/60 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-(--muted-foreground)">
          {label}
        </span>
        {heart && (
          <span className="rounded-md border border-(--accent)/35 bg-(--accent)/10 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.16em] text-(--accent)">
            the heart
          </span>
        )}
        {sha && (
          <a
            href={REPO_COMMIT(sha)}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[10.5px] text-(--muted-foreground) hover:bg-(--muted)/60 hover:text-(--accent) transition-colors"
          >
            <Code2 className="size-3" />
            {sha}
            <ExternalLink className="size-2.5" />
          </a>
        )}
      </div>
      <p className="text-[13.5px] leading-7 text-(--muted-foreground)">{body}</p>
      {link && linkLabel && (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-flex items-center gap-1 font-mono text-[11.5px] text-(--accent) hover:underline"
        >
          <Code2 className="size-3" />
          {linkLabel}
          <ExternalLink className="size-2.5" />
        </a>
      )}
    </li>
  );
}

function InterestingCallouts() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Callout
        tone="accent"
        title="Speaker-aware chunking, the unsexy gold"
        body="Every RAG tutorial defaults to recursive 400-token chunks. For transcripts that throws away free structural signal — the prepared/Q&A divide, the CEO/CFO/Analyst role labels, the back-and-forth conversational shape. Speaker-aware chunking respects all of it. Result: the corpus answers questions like 'show me the most evasive CFO Q&A answers about AI capex' with a one-line metadata filter instead of an LLM scan."
      />
      <Callout
        tone="amber"
        title="LLM-as-extractor enrichment"
        body="One Sonnet call per chunk at ingest extracts hedging_score + sentiment + topics. ~$3.85 amortized — and now every query gets those signals for free, forever. The 64% gap between prepared (0.20 hedging) and Q&A (0.33 hedging) is the calibration validating that the model is actually picking up on uncertain language."
      />
      <Callout
        tone="violet"
        title="Hybrid retrieval, both lanes win"
        body="BM25 catches 'free cash flow' and 'gross margin' (exact phrases that the dense embedding sometimes paraphrases out). Dense catches 'how does Apple describe China risk' (semantic intent the keyword lane misses entirely — BM25 returned 0 candidates on that one). RRF merges them. The compare-view smoke test made this case explicit: dense rescued the cross-company query when BM25 returned zero hits."
      />
      <Callout
        tone="rose"
        title="Honest eval saturation"
        body="The rerank-on/off and hedging-filter ablations both hit recall@5 = 1.000. The honest reading: at 1,097 chunks with the strong (ticker, year, quarter) metadata pre-filters every eval case carries, ticker-level recall is at ceiling regardless of rerank. Their real lift is in theme coverage + LLM judge, and the corpus would need to grow ~10x before HNSW vs seq scan even starts to matter."
      />
    </div>
  );
}

function Callout({
  tone,
  title,
  body,
}: {
  tone: "accent" | "amber" | "violet" | "rose";
  title: string;
  body: string;
}) {
  const COLOR = {
    accent: "oklch(0.62 0.20 145)",
    amber: "oklch(0.68 0.18 70)",
    violet: "oklch(0.6 0.18 320)",
    rose: "oklch(0.65 0.18 10)",
  }[tone];
  return (
    <div
      className="rounded-2xl border bg-(--card)/55 p-5"
      style={{
        borderColor: COLOR,
        backgroundImage: `linear-gradient(180deg, ${COLOR}1f 0%, transparent 80%)`,
      }}
    >
      <h3
        className="text-[12.5px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: COLOR }}
      >
        {title}
      </h3>
      <p className="mt-2 text-[13.5px] leading-7 text-(--muted-foreground)">{body}</p>
    </div>
  );
}

function TechStack() {
  return (
    <div className="rounded-2xl border border-(--border) bg-(--card)/55 p-5 md:p-6">
      <ul className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[13px]">
        <TechRow label="Language" value="Python 3.11+ (runs on 3.14 with a REST workaround for voyageai)" />
        <TechRow label="Packaging" value="uv — lock file, fast installs, reproducible" />
        <TechRow label="Database" value="Postgres 16 + pgvector (local docker compose, port 5433)" />
        <TechRow label="Ingest" value="HuggingFace datasets — Rogersurf/earnings-call-transcripts" />
        <TechRow label="Chunking" value="Speaker-aware, 200-token floor, 600-token ceiling" />
        <TechRow label="Embeddings" value="Voyage voyage-finance-2 (1024-dim, finance-tuned) via REST" />
        <TechRow label="Retrieval" value="BM25 (ts_rank) + dense (pgvector <=>) → RRF → Cohere Rerank 3.5" />
        <TechRow label="Synthesis" value="Claude Opus 4.6 with cache_control on the system prompt" />
        <TechRow label="Enrichment" value="Claude Sonnet 4.5 (one shot per chunk, ~$3.85 amortized)" />
        <TechRow label="Guardrails" value="Per-query token caps + session cost ceiling + cascade + breaker" />
        <TechRow label="Evaluation" value="Braintrust, 30-case stratified suite, LLM-as-judge" />
        <TechRow label="UI" value="Next.js 16 (App Router) + Tailwind v4 + Radix-on-Tailwind primitives + Framer Motion" />
        <TechRow label="Observability" value="Braintrust trace per retrieval + LLM call" />
        <TechRow label="Security" value="OWASP LLM Top 10 mapped in SECURITY.md; sanitize_retrieved_chunk on every prompt injection surface" />
      </ul>
    </div>
  );
}

function TechRow({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex flex-col gap-0.5">
      <span className="text-[10.5px] uppercase tracking-[0.16em] text-(--muted-foreground)">
        {label}
      </span>
      <span className="text-(--foreground)">{value}</span>
    </li>
  );
}

function EvalSummary() {
  return (
    <div className="overflow-hidden rounded-2xl border border-(--border) bg-(--card)/55">
      <table className="w-full text-[13px]">
        <thead className="text-left text-[11px] uppercase tracking-[0.14em] text-(--muted-foreground)">
          <tr className="border-b border-(--border)">
            <th className="p-3">metric</th>
            <th className="p-3 text-right">overall</th>
            <th className="p-3 text-right">single_call</th>
            <th className="p-3 text-right">multi_quarter</th>
            <th className="p-3 text-right">cross_company</th>
          </tr>
        </thead>
        <tbody className="font-mono tabular-nums">
          <EvalRow metric="recall@5" overall="1.000" sc="1.000" mq="1.000" cc="1.000" />
          <EvalRow metric="MRR" overall="1.000" sc="1.000" mq="1.000" cc="1.000" />
          <EvalRow metric="theme coverage" overall="0.917" sc="0.950" mq="0.925" cc="0.875" />
          <EvalRow metric="citation min satisfied" overall="1.000" sc="1.000" mq="1.000" cc="1.000" />
          <EvalRow metric="LLM judge (0–1)" overall="0.938" sc="0.993" mq="0.933" cc="0.887" highlight />
        </tbody>
      </table>
      <p className="border-t border-(--border) px-4 py-3 text-[12px] leading-relaxed text-(--muted-foreground)">
        n = 30 cases, ~$4.50 in Opus synthesis + LLM judge. The judge rates
        every answer 0–5 on groundedness, completeness, and clarity, mapped to
        the 0–1 score above. Cross-company answers grade lowest (0.887) — the
        bar is higher for synthesis that has to honestly contrast two
        companies vs. pulling from one.
      </p>
    </div>
  );
}

function EvalRow({
  metric,
  overall,
  sc,
  mq,
  cc,
  highlight,
}: {
  metric: string;
  overall: string;
  sc: string;
  mq: string;
  cc: string;
  highlight?: boolean;
}) {
  return (
    <tr
      className={
        "border-b border-(--border) last:border-b-0 " +
        (highlight ? "bg-(--accent)/10" : "")
      }
    >
      <td className="p-3 font-sans text-(--foreground)">{metric}</td>
      <td className="p-3 text-right font-semibold">{overall}</td>
      <td className="p-3 text-right">{sc}</td>
      <td className="p-3 text-right">{mq}</td>
      <td className="p-3 text-right">{cc}</td>
    </tr>
  );
}

function WhatsNext() {
  return (
    <ul className="space-y-3 text-[13.5px] leading-7 text-(--muted-foreground)">
      <li>
        <strong className="text-(--foreground)">Deploy to Vercel + a hosted backend.</strong>{" "}
        The UI is local-only right now. Vercel for the frontend; Railway or
        Fly.io for the FastAPI process; Neon for managed Postgres + pgvector.
        Drop the local-only ports and ship a real URL.
      </li>
      <li>
        <strong className="text-(--foreground)">Voyage 3-large vs finance-2 A/B.</strong>{" "}
        The third planned eval ablation. Needs a one-time re-embed of the
        whole corpus with voyage-3-large into a parallel column, then a swap
        at retrieval to compare recall@5 on the same 30-case suite. Will
        surface whether the finance-tuned model actually buys precision on
        this corpus.
      </li>
      <li>
        <strong className="text-(--foreground)">Expand to 13 quarters.</strong>{" "}
        Q4 2023 → Q1 2026 would let the multi-quarter eval cases stretch
        further back and surface the pre/post-ChatGPT-2.0 framing shift on
        AI capex.
      </li>
      <li>
        <strong className="text-(--foreground)">NBA sibling project.</strong>{" "}
        The same author shipped a hybrid-retrieval RAG with text-to-SQL +
        prose routing for the 2025-26 NBA season —{" "}
        <a
          href="https://github.com/ZayM511/NBA-Scouting-and-Stats-RAG-Pipeline"
          target="_blank"
          rel="noopener noreferrer"
          className="text-(--accent) hover:underline"
        >
          Ball Knowledge Oracle
        </a>
        . Pair this project (depth: metadata-rich retrieval + LLM enrichment)
        with that one (breadth: routing, text-to-SQL, hybrid paths) for a
        portfolio that signals both kinds of judgment.
      </li>
    </ul>
  );
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <span className="text-[10.5px] uppercase tracking-[0.18em] text-(--muted-foreground)">
        {label}
      </span>
      <div className="h-px flex-1 bg-(--border)" />
    </div>
  );
}

function PageFooter() {
  return (
    <footer className="border-t border-(--border) pt-6 text-xs text-(--muted-foreground)">
      <p>
        Source on{" "}
        <a
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-(--accent) hover:underline"
        >
          GitHub
        </a>
        . Architecture diagram, eval numbers, README, and 9 phase commits all
        live there. Built by{" "}
        <strong className="text-(--foreground)">Isaiah Malone</strong>.
      </p>
      <p className="mt-2">
        <Link href="/" className="text-(--accent) hover:underline">
          ← Back to Ask
        </Link>
      </p>
    </footer>
  );
}
