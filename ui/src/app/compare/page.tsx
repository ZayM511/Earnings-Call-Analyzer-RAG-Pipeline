"use client";

import * as React from "react";
import Link from "next/link";
import { Send, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AnswerView } from "@/components/answer-view";
import { ask, type AskResponse } from "@/lib/api";

const MAG7 = ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"] as const;

interface Column {
  ticker: string;
  state: "idle" | "loading" | "done" | "error";
  result?: AskResponse;
  error?: string;
}

export default function ComparePage() {
  const [question, setQuestion] = React.useState(
    "How is AI capex framed and what is the 2025 outlook?",
  );
  const [columns, setColumns] = React.useState<Column[]>([
    { ticker: "MSFT", state: "idle" },
    { ticker: "GOOGL", state: "idle" },
    { ticker: "AMZN", state: "idle" },
  ]);

  const runColumn = async (idx: number) => {
    const col = columns[idx];
    setColumns((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, state: "loading", error: undefined } : c)),
    );
    try {
      const tickers = col.ticker === "GOOGL" ? ["GOOGL", "GOOG"] : [col.ticker];
      const result = await ask({
        question: question.trim(),
        tickers,
        top_k: 8,
      });
      setColumns((prev) =>
        prev.map((c, i) => (i === idx ? { ...c, state: "done", result } : c)),
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setColumns((prev) =>
        prev.map((c, i) => (i === idx ? { ...c, state: "error", error: msg } : c)),
      );
    }
  };

  const runAll = () => {
    columns.forEach((_, i) => void runColumn(i));
  };

  const setColumnTicker = (idx: number, ticker: string) =>
    setColumns((prev) =>
      prev.map((c, i) => (i === idx ? { ticker, state: "idle" } : c)),
    );

  const addColumn = () =>
    setColumns((prev) => [...prev, { ticker: "META", state: "idle" }]);

  const removeColumn = (idx: number) =>
    setColumns((prev) => prev.filter((_, i) => i !== idx));

  return (
    <div className="flex flex-col flex-1 min-h-screen bg-(--background)">
      <header className="border-b border-(--border) bg-(--card)/80 backdrop-blur">
        <div className="mx-auto max-w-7xl px-6 py-4 flex flex-wrap items-baseline gap-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="inline-flex size-7 items-center justify-center rounded-md bg-(--accent) text-(--accent-foreground) text-xs font-semibold">
              EC
            </span>
            <span className="text-base font-semibold tracking-tight">Earnings Call Analyzer</span>
          </Link>
          <span className="text-xs text-(--muted-foreground)">Compare view</span>
          <nav className="ml-auto flex items-center gap-3 text-sm">
            <Link href="/" className="text-(--muted-foreground) hover:text-(--accent)">
              Ask
            </Link>
            <Link href="/compare" className="text-(--foreground) font-medium hover:text-(--accent)">
              Compare
            </Link>
          </nav>
        </div>
      </header>

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

                <div className="flex-1 overflow-hidden">
                  {col.state === "idle" && (
                    <p className="text-sm text-(--muted-foreground)">
                      Press <em>Ask</em> or <em>Run all</em> to fetch this company&apos;s answer.
                    </p>
                  )}
                  {col.state === "loading" && (
                    <div className="flex items-center gap-2 text-sm text-(--muted-foreground)">
                      <Loader2 className="size-4 animate-spin" />
                      <span>Synthesizing…</span>
                    </div>
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
