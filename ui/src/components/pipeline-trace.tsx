"use client";

import * as React from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  Brain,
  Check,
  ChevronRight,
  Database,
  FileText,
  Layers,
  Loader2,
  MessageCircle,
  Search,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Live RAG pipeline visualization. Walks six stages while a query is in
 * flight; finalizes when the API resolves. Mirrors the architecture diagram:
 *
 *   User Question
 *   -> BM25 + Dense vector search (with metadata pre-filter)
 *   -> Merge candidates (RRF)
 *   -> Cohere Rerank
 *   -> Claude Opus synthesis
 *   -> Cited Answer
 */

export type TraceState = "idle" | "running" | "done" | "error";
export type StageIndex = 0 | 1 | 2 | 3 | 4 | 5;

export interface PipelineTraceFilters {
  tickers?: string[];
  year?: number;
  quarter?: string;
}

export interface PipelineTraceProps {
  state: TraceState;
  activeStage?: StageIndex;
  filters?: PipelineTraceFilters;
  finalModel?: string;
  costUsd?: number | null;
  latencyMs?: number | null;
  className?: string;
}

interface StageDef {
  label: string;
  sublabel: string;
  Icon: typeof MessageCircle;
  tone: { hue: string; ring: string };
}

// Tones match the user-provided build-guide diagram screenshot.
const SLATE = { hue: "oklch(0.55 0.02 270)", ring: "oklch(0.55 0.02 270 / 0.45)" };
const CORAL = { hue: "oklch(0.62 0.18 25)", ring: "oklch(0.62 0.18 25 / 0.48)" };
const VIOLET = { hue: "oklch(0.6 0.18 320)", ring: "oklch(0.6 0.18 320 / 0.48)" };
const GREEN = { hue: "oklch(0.62 0.20 145)", ring: "oklch(0.62 0.20 145 / 0.48)" };

const STAGES: StageDef[] = [
  { label: "User Question", sublabel: "filters surface here", Icon: MessageCircle, tone: SLATE },
  { label: "BM25 + Dense", sublabel: "top 50 each", Icon: Search, tone: CORAL },
  { label: "Merge", sublabel: "reciprocal rank fusion", Icon: Layers, tone: VIOLET },
  { label: "Cohere Rerank", sublabel: "rerank-v3.5 · top 5–10", Icon: Sparkles, tone: VIOLET },
  { label: "Claude Synthesis", sublabel: "Opus 4.6 · cited markdown", Icon: Brain, tone: GREEN },
  { label: "Cited Answer", sublabel: "inline citations", Icon: FileText, tone: SLATE },
];

/**
 * Custom hook: while in "running" state, advance `activeStage` forward
 * automatically based on rough per-stage budgets. Synthesis (stage 4) is
 * sticky — the cursor parks there until the parent flips state to "done".
 */
export function usePipelineTimeline(state: TraceState): {
  activeStage: StageIndex;
  reset: () => void;
} {
  const [stage, setStage] = React.useState<StageIndex>(0);

  React.useEffect(() => {
    if (state !== "running") {
      if (state === "done") setStage(5);
      if (state === "idle") setStage(0);
      return;
    }
    // Per-stage budgets (ms). Stages 0-3 walk quickly; stage 4 (synthesis)
    // sticks until the API call resolves (parent sets state to "done").
    const transitions: { at: number; to: StageIndex }[] = [
      { at: 250, to: 1 },
      { at: 1300, to: 2 },
      { at: 1700, to: 3 },
      { at: 2400, to: 4 },
    ];
    const timers = transitions.map(({ at, to }) =>
      window.setTimeout(() => setStage(to), at),
    );
    return () => {
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, [state]);

  const reset = React.useCallback(() => setStage(0), []);
  return { activeStage: stage, reset };
}

/**
 * Render-only component. Parent owns the timeline (see usePipelineTimeline).
 */
export function PipelineTrace({
  state,
  activeStage = 0,
  filters,
  finalModel,
  costUsd,
  latencyMs,
  className,
}: PipelineTraceProps) {
  const reduce = useReducedMotion();
  const showFilters =
    !!filters &&
    ((filters.tickers && filters.tickers.length > 0) || filters.year !== undefined || filters.quarter !== undefined);

  return (
    <div
      data-testid="pipeline-trace"
      data-state={state}
      className={cn(
        "rounded-xl border border-(--border) bg-(--card)/70 p-4 md:p-5 backdrop-blur-sm",
        className,
      )}
    >
      <div className="flex items-baseline justify-between text-xs text-(--muted-foreground) mb-3">
        <span className="uppercase tracking-wider">RAG pipeline</span>
        {state === "done" && (
          <span className="flex flex-wrap items-center gap-2 tabular-nums">
            {finalModel && <span className="font-mono">{finalModel}</span>}
            {typeof costUsd === "number" && <span>${costUsd.toFixed(3)}</span>}
            {typeof latencyMs === "number" && <span>{(latencyMs / 1000).toFixed(1)}s</span>}
          </span>
        )}
      </div>

      <ol
        className="flex flex-col lg:flex-row lg:items-stretch gap-2 lg:gap-1.5"
        aria-label="RAG pipeline stages"
      >
        {STAGES.map((stage, idx) => {
          const status: "pending" | "active" | "done" =
            state === "idle"
              ? idx === 0
                ? "active"
                : "pending"
              : state === "done"
                ? "done"
                : idx < activeStage
                  ? "done"
                  : idx === activeStage
                    ? "active"
                    : "pending";

          return (
            <React.Fragment key={stage.label}>
              <StageCard
                stage={stage}
                index={idx}
                status={status}
                reduce={!!reduce}
              />
              {idx < STAGES.length - 1 && <ArrowBetween status={status} />}
            </React.Fragment>
          );
        })}
      </ol>

      {/* Metadata pre-filter callout — sits below stage 2. */}
      {showFilters && (
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.4 }}
          className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-(--muted-foreground)"
        >
          <span className="italic">↳ metadata pre-filter narrows the corpus before vector math:</span>
          {filters?.tickers?.map((t) => (
            <span
              key={t}
              className="rounded-md border border-(--accent)/30 bg-(--accent)/10 px-1.5 py-0.5 text-(--accent) font-medium"
            >
              {t}
            </span>
          ))}
          {filters?.year !== undefined && (
            <span className="rounded-md border border-(--accent)/30 bg-(--accent)/10 px-1.5 py-0.5 text-(--accent) tabular-nums">
              {filters.year}
            </span>
          )}
          {filters?.quarter && (
            <span className="rounded-md border border-(--accent)/30 bg-(--accent)/10 px-1.5 py-0.5 text-(--accent)">
              {filters.quarter}
            </span>
          )}
        </motion.div>
      )}
    </div>
  );
}

function StageCard({
  stage,
  index,
  status,
  reduce,
}: {
  stage: StageDef;
  index: number;
  status: "pending" | "active" | "done";
  reduce: boolean;
}) {
  const { hue, ring } = stage.tone;
  const isActive = status === "active";
  const isDone = status === "done";

  return (
    <motion.li
      data-testid={`stage-${index}`}
      data-status={status}
      initial={reduce ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: 0.04 * index }}
      className={cn(
        "relative flex flex-1 min-w-[140px] flex-col gap-1 rounded-lg border bg-(--card) px-3 py-2.5 transition-all",
        isActive && "shadow-[0_0_0_3px_var(--ring-color)]",
        status === "pending" && "opacity-55",
      )}
      style={
        {
          borderColor: isDone || isActive ? hue : "var(--border)",
          // soft inner tint
          backgroundImage:
            isActive || isDone
              ? `linear-gradient(180deg, ${hue}1a 0%, transparent 80%)`
              : undefined,
          // ring color used by the box-shadow above (named CSS var for clean apply)
          ["--ring-color" as string]: ring,
        } as React.CSSProperties
      }
    >
      <div className="flex items-center gap-2 text-[12.5px]">
        <span
          className="inline-flex size-5 items-center justify-center rounded-md"
          style={{
            background: isDone || isActive ? hue : "var(--muted)",
            color: isDone || isActive ? "white" : "var(--muted-foreground)",
          }}
        >
          {isDone ? <Check className="size-3" /> : isActive ? <stage.Icon className="size-3" /> : <stage.Icon className="size-3" />}
        </span>
        <span
          className="font-medium tracking-tight"
          style={{ color: isDone || isActive ? hue : undefined }}
        >
          {stage.label}
        </span>
        {isActive && !reduce && (
          <Loader2
            className="ml-auto size-3 animate-spin"
            style={{ color: hue }}
            aria-hidden="true"
          />
        )}
      </div>
      <span className="text-[10.5px] text-(--muted-foreground) leading-tight">
        {stage.sublabel}
      </span>
    </motion.li>
  );
}

function ArrowBetween({
  status,
}: {
  status: "pending" | "active" | "done";
}) {
  // Show a horizontal arrow on lg; a downward chevron stack on mobile.
  return (
    <li
      aria-hidden="true"
      className="flex items-center justify-center lg:px-0.5"
    >
      <ChevronRight
        className={cn(
          "hidden lg:block size-4 transition-colors",
          status === "done" || status === "active"
            ? "text-(--accent)"
            : "text-(--muted-foreground)/40",
        )}
      />
      <ChevronRight
        className={cn(
          "lg:hidden size-3 rotate-90 transition-colors",
          status === "done" || status === "active"
            ? "text-(--accent)"
            : "text-(--muted-foreground)/40",
        )}
      />
    </li>
  );
}
