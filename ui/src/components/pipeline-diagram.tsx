"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  Brain,
  ChevronRight,
  Database,
  FileText,
  Layers,
  MessageCircle,
  Search,
  Sparkles,
  Tag,
  Workflow,
} from "lucide-react";

/**
 * Static, full-system pipeline diagram for the /how-i-made-this page.
 *
 * Two visual bands:
 *   1. OFFLINE: ingest -> chunk -> metadata -> Claude enrichment -> embed -> index
 *   2. ONLINE:  user question -> BM25 + Dense (with metadata pre-filter)
 *               -> merge -> Cohere rerank -> Opus synthesis -> cited answer
 *
 * Observability strip at the bottom (Braintrust).
 *
 * Color palette intentionally rhymes with PipelineTrace so the live and
 * static diagrams read as the same system.
 */

const COLORS = {
  slate: "oklch(0.55 0.02 270)",
  blue: "oklch(0.62 0.16 250)",
  pink: "oklch(0.6 0.18 350)",
  coral: "oklch(0.62 0.18 25)",
  violet: "oklch(0.6 0.18 320)",
  green: "oklch(0.62 0.20 145)",
  amber: "oklch(0.68 0.18 70)",
  observability: "oklch(0.55 0.20 295)",
};

export function PipelineDiagram() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="relative overflow-hidden rounded-2xl border border-(--border) bg-(--card)/60 p-5 md:p-7 backdrop-blur-sm"
    >
      <h3 className="text-center text-lg font-semibold tracking-tight">
        Earnings Call Analyzer — RAG Pipeline
      </h3>
      <p className="text-center text-xs italic text-(--muted-foreground) mt-1">
        Offline: ingest + index &nbsp;|&nbsp; Online: query + answer
      </p>

      {/* ---- OFFLINE BAND ---------------------------------------------- */}
      <BandLabel color={COLORS.blue} text="OFFLINE (run once when data changes)" />
      <ol className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mt-3">
        <DiagramNode
          num={1}
          title="Ingest Transcripts"
          subtitle="HuggingFace + Motley Fool"
          icon={Database}
          color={COLORS.blue}
        />
        <DiagramNode
          num={2}
          title="Speaker-Aware Chunker"
          subtitle="regex by speaker turn"
          icon={Workflow}
          color={COLORS.pink}
        />
        <DiagramNode
          num={3}
          title="Metadata Extraction"
          subtitle="ticker, quarter, role, section"
          icon={Tag}
          color={COLORS.pink}
        />
        <DiagramNode
          num={4}
          title="Claude LLM Enrichment"
          subtitle="hedging, sentiment, topics"
          icon={Brain}
          color={COLORS.green}
        />
        <DiagramNode
          num={5}
          title="Embed"
          subtitle="voyage-finance-2 · 1024-dim"
          icon={Sparkles}
          color={COLORS.amber}
        />
        <DiagramNode
          num={6}
          title="Index"
          subtitle="Postgres + pgvector (HNSW)"
          icon={Layers}
          color={COLORS.amber}
        />
      </ol>

      {/* ---- ONLINE BAND ----------------------------------------------- */}
      <div className="mt-8" />
      <BandLabel color={COLORS.coral} text="ONLINE (per user query)" />

      <div className="mt-3 grid grid-cols-1 lg:grid-cols-[auto_1fr_auto_auto_auto_auto] gap-2 lg:items-stretch">
        <NodeOnly title="User Question" icon={MessageCircle} color={COLORS.slate} />
        <Arrow />

        <div className="grid grid-cols-1 gap-1.5 relative">
          <NodeOnly
            title="BM25 keyword search"
            sub="top 50"
            icon={Search}
            color={COLORS.coral}
          />
          <NodeOnly
            title="Dense vector search"
            sub="top 50 · voyage-finance-2"
            icon={Database}
            color={COLORS.coral}
          />
          {/* metadata-pre-filter callout */}
          <p className="text-[10.5px] italic text-(--muted-foreground) leading-snug max-w-xs mt-1">
            ↳ metadata pre-filter (ticker · quarter · year) dramatically narrows the search
          </p>
        </div>

        <Arrow />
        <NodeOnly title="Merge candidates" sub="RRF" icon={Layers} color={COLORS.violet} />
        <Arrow />
        <NodeOnly
          title="Cohere Rerank"
          sub="rerank-v3.5 · top 5–10"
          icon={Sparkles}
          color={COLORS.violet}
        />
        <Arrow />
        <NodeOnly
          title="Claude Opus 4.6"
          sub="cited synthesis"
          icon={Brain}
          color={COLORS.green}
        />
        <Arrow />
        <NodeOnly title="Cited Answer" icon={FileText} color={COLORS.slate} />
      </div>

      {/* ---- OBSERVABILITY STRIP -------------------------------------- */}
      <div
        className="mt-7 rounded-lg border px-4 py-3 text-[12px] text-(--foreground)"
        style={{
          borderColor: COLORS.observability,
          backgroundImage: `linear-gradient(180deg, ${COLORS.observability}26 0%, transparent 80%)`,
        }}
      >
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider" style={{ color: COLORS.observability }}>
          <Workflow className="size-3.5" />
          Observability
        </div>
        <p className="mt-1 leading-relaxed">
          Braintrust logs every retrieval + LLM call. A 30-query eval set
          (stratified across single-call / multi-quarter / cross-company)
          runs through this pipeline after every meaningful change and tracks
          recall@5, MRR, theme coverage, and an LLM-as-judge score across
          experiments.
        </p>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Building blocks
// ---------------------------------------------------------------------------

function BandLabel({ color, text }: { color: string; text: string }) {
  return (
    <p
      className="mt-5 text-[11px] font-semibold uppercase tracking-[0.18em]"
      style={{ color }}
    >
      {text}
    </p>
  );
}

function DiagramNode({
  num,
  title,
  subtitle,
  icon: Icon,
  color,
}: {
  num: number;
  title: string;
  subtitle: string;
  icon: typeof Database;
  color: string;
}) {
  return (
    <li
      className="rounded-lg border bg-(--card) p-3 flex flex-col gap-1"
      style={{
        borderColor: color,
        backgroundImage: `linear-gradient(180deg, ${color}1f 0%, transparent 75%)`,
      }}
    >
      <div className="flex items-center gap-1.5 text-[11px] font-semibold" style={{ color }}>
        <span
          className="inline-flex size-4 items-center justify-center rounded-sm text-[9px]"
          style={{ background: color, color: "white" }}
        >
          {num}
        </span>
        <Icon className="size-3.5" />
      </div>
      <p className="text-[12.5px] font-semibold leading-tight text-(--foreground)">
        {title}
      </p>
      <p className="text-[10.5px] italic text-(--muted-foreground) leading-tight">
        {subtitle}
      </p>
    </li>
  );
}

function NodeOnly({
  title,
  sub,
  icon: Icon,
  color,
}: {
  title: string;
  sub?: string;
  icon: typeof Database;
  color: string;
}) {
  return (
    <div
      className="rounded-lg border bg-(--card) px-3 py-2 flex flex-col justify-center min-w-[120px]"
      style={{
        borderColor: color,
        backgroundImage: `linear-gradient(180deg, ${color}1f 0%, transparent 75%)`,
      }}
    >
      <div className="flex items-center gap-1.5 text-[11.5px] font-semibold" style={{ color }}>
        <Icon className="size-3.5" />
        {title}
      </div>
      {sub && (
        <span className="mt-0.5 text-[10.5px] italic text-(--muted-foreground) leading-tight">
          {sub}
        </span>
      )}
    </div>
  );
}

function Arrow() {
  return (
    <div className="flex items-center justify-center lg:px-0.5">
      <ChevronRight className="hidden lg:block size-4 text-(--muted-foreground)" />
      <ChevronRight className="lg:hidden size-3 rotate-90 text-(--muted-foreground)" />
    </div>
  );
}
