"use client";

import * as React from "react";
import { ChevronRight, Loader2, Search, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FilterBar, type FilterState } from "@/components/filter-bar";
import { SampleChips } from "@/components/sample-chips";
import { AnswerView } from "@/components/answer-view";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  PipelineTrace,
  usePipelineTimeline,
  type TraceState,
} from "@/components/pipeline-trace";
import { ask, type AskResponse } from "@/lib/api";

export function AskForm() {
  const [question, setQuestion] = React.useState("");
  const [filters, setFilters] = React.useState<FilterState>({ tickers: [] });
  const [traceState, setTraceState] = React.useState<TraceState>("idle");
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<AskResponse | null>(null);
  const { activeStage } = usePipelineTimeline(traceState);

  const loading = traceState === "running";

  const submit = async () => {
    if (!question.trim() || loading) return;
    setTraceState("running");
    setError(null);
    setResult(null);
    try {
      const out = await ask({
        question: question.trim(),
        tickers: filters.tickers.length ? filters.tickers : undefined,
        year: filters.year,
        quarter: filters.quarter,
        top_k: 10,
      });
      setResult(out);
      setTraceState("done");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setTraceState("error");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <FilterBar value={filters} onChange={setFilters} />

      <SampleChips onPick={(q) => setQuestion(q)} />

      <div className="flex items-end gap-2">
        <div className="flex-1">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything about the Mag 7's 2024–2026 earnings calls..."
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            data-testid="ask-input"
            className="h-12 text-base"
          />
        </div>
        <Button
          onClick={submit}
          disabled={loading || !question.trim()}
          variant="accent"
          size="lg"
          data-testid="ask-submit"
        >
          {loading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          {loading ? "Searching 1,097 chunks…" : "Ask"}
        </Button>
      </div>

      {error && (
        <Card>
          <CardContent className="p-4 text-sm text-(--destructive)">
            {error}
          </CardContent>
        </Card>
      )}

      {(loading || result) && (
        <PipelineTrace
          state={traceState}
          activeStage={activeStage}
          filters={{
            tickers: filters.tickers.length ? filters.tickers : undefined,
            year: filters.year,
            quarter: filters.quarter,
          }}
          finalModel={result?.model}
          costUsd={result?.cost_usd ?? null}
          latencyMs={result?.latency_ms ?? null}
        />
      )}


      {result && <AnswerCard result={result} />}
    </div>
  );
}

function AnswerCard({ result }: { result: AskResponse }) {
  return (
    <Card data-testid="answer-card">
      <CardContent className="p-6 space-y-6">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Badge variant="accent">{result.citations.length} citations</Badge>
          <Badge variant="default">{result.chunks.length} chunks retrieved</Badge>
          <Badge variant="default">
            <span className="tabular-nums">
              {result.input_tokens} in / {result.output_tokens} out
            </span>
          </Badge>
          <Badge variant="default">
            <span className="tabular-nums">${result.cost_usd.toFixed(4)}</span>
          </Badge>
          <Badge variant="default">
            <span className="tabular-nums">{(result.latency_ms / 1000).toFixed(1)}s</span>
          </Badge>
          <span className="ml-auto text-(--muted-foreground)">{result.model}</span>
        </div>

        <AnswerView result={result} />

        <details className="group text-xs text-(--muted-foreground)">
          <summary className="inline-flex w-fit items-center gap-1.5 cursor-pointer select-none rounded-md border border-(--border) bg-(--muted)/40 px-2.5 py-1.5 text-(--foreground) font-medium hover:border-(--accent)/45 hover:bg-(--accent)/10 hover:text-(--accent) transition-colors">
            <Search className="size-3.5" aria-hidden="true" />
            Inspect retrieved chunks
            <span className="rounded-sm bg-(--accent)/15 px-1.5 text-[10.5px] text-(--accent) tabular-nums">
              {result.chunks.length}
            </span>
            <ChevronRight
              className="size-3.5 transition-transform duration-200 group-open:rotate-90"
              aria-hidden="true"
            />
          </summary>
          <div className="mt-3 space-y-2">
            {result.chunks.map((c, i) => (
              <div
                key={c.chunk_id}
                className="rounded-md border border-(--border) p-3 text-sm"
                data-testid="chunk-row"
              >
                <div className="flex flex-wrap items-baseline gap-2 mb-1">
                  <span className="font-semibold text-(--foreground)">
                    {c.ticker} {c.quarter} {c.year}
                  </span>
                  <span className="text-(--muted-foreground)">
                    {c.speaker_name} ({c.speaker_role} / {c.section})
                  </span>
                  {c.rerank_score !== null && (
                    <span className="ml-auto tabular-nums text-(--muted-foreground)">
                      rerank {c.rerank_score.toFixed(3)}
                    </span>
                  )}
                  <span className="tabular-nums text-(--muted-foreground)">
                    hedge {(c.hedging_score ?? 0).toFixed(2)}
                  </span>
                </div>
                <div className="text-(--foreground) line-clamp-4">
                  <span className="text-(--muted-foreground)">#{i + 1}</span> {c.text}
                </div>
              </div>
            ))}
          </div>
        </details>
      </CardContent>
    </Card>
  );
}
