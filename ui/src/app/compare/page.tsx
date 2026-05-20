"use client";

import * as React from "react";
import { Send, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AnswerView } from "@/components/answer-view";
import { SiteHeader } from "@/components/site-header";
import { PipelineTrace, type TraceState, type StageIndex } from "@/components/pipeline-trace";
import { ask, type AskResponse } from "@/lib/api";

const MAG7 = ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"] as const;

interface Column {
  ticker: string;
  state: "idle" | "loading" | "done" | "error";
  /** Mapped to PipelineTrace.state — loading -> running. */
  traceStage: StageIndex;
  result?: AskResponse;
  error?: string;
}

function toTraceState(state: Column["state"]): TraceState {
  if (state === "loading") return "running";
  if (state === "done") return "done";
  if (state === "error") return "error";
  return "idle";
}

export default function ComparePage() {
  const [question, setQuestion] = React.useState(
    "How is AI capex framed and what is the 2025 outlook?",
  );
  const [columns, setColumns] = React.useState<Column[]>([
    { ticker: "MSFT", state: "idle", traceStage: 0 },
    { ticker: "GOOGL", state: "idle", traceStage: 0 },
    { ticker: "AMZN", state: "idle", traceStage: 0 },
  ]);

  const runColumn = async (idx: number) => {
    const col = columns[idx];
    setColumns((prev) =>
      prev.map((c, i) =>
        i === idx ? { ...c, state: "loading", traceStage: 0, error: undefined, result: undefined } : c,
      ),
    );
    // Independent per-column timeline — walk stages 0→4 while the request is
    // in flight; the final transition to stage 5 happens in the success path.
    const timers = [
      window.setTimeout(() => bumpStage(idx, 1), 250),
      window.setTimeout(() => bumpStage(idx, 2), 1300),
      window.setTimeout(() => bumpStage(idx, 3), 1700),
      window.setTimeout(() => bumpStage(idx, 4), 2400),
    ];
    try {
      const tickers = col.ticker === "GOOGL" ? ["GOOGL", "GOOG"] : [col.ticker];
      const result = await ask({
        question: question.trim(),
        tickers,
        top_k: 8,
      });
      timers.forEach((t) => window.clearTimeout(t));
      setColumns((prev) =>
        prev.map((c, i) => (i === idx ? { ...c, state: "done", traceStage: 5, result } : c)),
      );
    } catch (e) {
      timers.forEach((t) => window.clearTimeout(t));
      const msg = e instanceof Error ? e.message : String(e);
      setColumns((prev) =>
        prev.map((c, i) => (i === idx ? { ...c, state: "error", error: msg } : c)),
      );
    }
  };

  const bumpStage = (idx: number, stage: StageIndex) =>
    setColumns((prev) =>
      prev.map((c, i) =>
        i === idx && c.state === "loading" ? { ...c, traceStage: stage } : c,
      ),
    );

  const runAll = () => {
    columns.forEach((_, i) => void runColumn(i));
  };

  const setColumnTicker = (idx: number, ticker: string) =>
    setColumns((prev) =>
      prev.map((c, i) => (i === idx ? { ticker, state: "idle", traceStage: 0 } : c)),
    );

  const addColumn = () =>
    setColumns((prev) => [...prev, { ticker: "META", state: "idle", traceStage: 0 }]);

  const removeColumn = (idx: number) =>
    setColumns((prev) => prev.filter((_, i) => i !== idx));

  return (
    <div className="flex flex-col flex-1 min-h-screen bg-(--background)">
      <SiteHeader />

      <main className="mx-auto w-full max-w-7xl px-6 py-10 flex flex-col gap-6">
        <section className="space-y-2">
          <h1 className="text-2xl md:text-3xl font-medium tracking-tight">
            Compare across companies
          </h1>
          <p className="text-(--muted-foreground) max-w-3xl text-sm md:text-base">
            Pick 2–4 Mag 7 tickers and ask the same question. Each column runs its
            own retrieval + synthesis call. Citations are clickable per column.
          </p>
        </section>

        <div className="flex flex-col gap-3">
          <div className="flex items-end gap-2">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="One question, asked across companies..."
              className="h-11 text-base"
              data-testid="compare-input"
            />
            <Button onClick={runAll} variant="accent" size="lg" data-testid="compare-run-all">
              <Send className="size-4" />
              Run all
            </Button>
          </div>
          <div className="flex items-center gap-2 text-xs text-(--muted-foreground)">
            <span>Active columns:</span>
            {columns.map((c, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-md border border-(--border) bg-(--muted) px-1.5 py-0.5"
              >
                {c.ticker}
                <button
                  type="button"
                  onClick={() => removeColumn(i)}
                  className="hover:text-(--destructive)"
                  aria-label={`Remove ${c.ticker}`}
                >
                  <X className="size-3" />
                </button>
              </span>
            ))}
            {columns.length < 4 && (
              <Button variant="ghost" size="sm" onClick={addColumn}>
                + Add column
              </Button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
          {columns.map((col, i) => (
            <Card key={i} data-testid={`compare-col-${col.ticker}`} className="flex flex-col">
              <CardContent className="p-4 flex flex-col gap-3 flex-1">
                <div className="flex items-center gap-2">
                  <select
                    value={col.ticker}
                    onChange={(e) => setColumnTicker(i, e.target.value)}
                    className="rounded-md border border-(--border) bg-(--background) px-2 py-1 text-sm font-semibold"
                    data-testid={`compare-col-select-${i}`}
                  >
                    {MAG7.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => runColumn(i)}
                    disabled={col.state === "loading" || !question.trim()}
                  >
                    {col.state === "loading" ? (
                      <Loader2 className="size-3 animate-spin" />
                    ) : (
                      <Send className="size-3" />
                    )}
                    Ask
                  </Button>
                  {col.result && (
                    <div className="ml-auto flex items-center gap-1 text-xs text-(--muted-foreground)">
                      <Badge variant="default">
                        <span className="tabular-nums">{col.result.citations.length} cites</span>
                      </Badge>
                      <Badge variant="default">
                        <span className="tabular-nums">${col.result.cost_usd.toFixed(3)}</span>
                      </Badge>
                    </div>
                  )}
                </div>

                {(col.state === "loading" || col.state === "done") && (
                  <PipelineTrace
                    state={toTraceState(col.state)}
                    activeStage={col.traceStage}
                    filters={{
                      tickers: col.ticker === "GOOGL" ? ["GOOGL", "GOOG"] : [col.ticker],
                    }}
                    finalModel={col.result?.model}
                    costUsd={col.result?.cost_usd ?? null}
                    latencyMs={col.result?.latency_ms ?? null}
                  />
                )}

                <div className="flex-1 overflow-hidden">
                  {col.state === "idle" && (
                    <p className="text-sm text-(--muted-foreground)">
                      Press <em>Ask</em> or <em>Run all</em> to fetch this company&apos;s answer.
                    </p>
                  )}
                  {col.state === "error" && (
                    <p className="text-sm text-(--destructive)">{col.error}</p>
                  )}
                  {col.state === "done" && col.result && (
                    <div className="max-h-[60vh] overflow-y-auto pr-2 text-sm">
                      <AnswerView result={col.result} />
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}
