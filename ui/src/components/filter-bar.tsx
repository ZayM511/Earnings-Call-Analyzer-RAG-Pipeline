"use client";

import * as React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const MAG7 = ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"] as const;
const QUARTERS = ["Q1", "Q2", "Q3", "Q4"] as const;
const YEARS = [2024, 2025, 2026] as const;

export interface FilterState {
  tickers: string[];
  year?: number;
  quarter?: string;
}

interface Props {
  value: FilterState;
  onChange: (next: FilterState) => void;
}

export function FilterBar({ value, onChange }: Props) {
  const toggleTicker = (t: string) => {
    const has = value.tickers.includes(t);
    onChange({ ...value, tickers: has ? value.tickers.filter((x) => x !== t) : [...value.tickers, t] });
  };

  const setYear = (y: number | undefined) => onChange({ ...value, year: y });
  const setQuarter = (q: string | undefined) => onChange({ ...value, quarter: q });

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-(--border) bg-(--card) p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-xs uppercase tracking-wide text-(--muted-foreground) mr-2">Companies</span>
        {MAG7.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => toggleTicker(t)}
            className={
              "rounded-md border px-2 py-0.5 text-xs font-medium transition-colors " +
              (value.tickers.includes(t)
                ? "bg-(--accent)/15 text-(--accent) border-(--accent)/30"
                : "bg-(--muted) text-(--muted-foreground) border-(--border) hover:border-(--accent)/30 hover:text-(--accent)")
            }
            data-testid={`ticker-${t}`}
          >
            {t}
          </button>
        ))}
        {value.tickers.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => onChange({ ...value, tickers: [] })}>
            Clear
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs uppercase tracking-wide text-(--muted-foreground) mr-1">Year</span>
          {YEARS.map((y) => (
            <button
              key={y}
              type="button"
              onClick={() => setYear(value.year === y ? undefined : y)}
              className={
                "rounded-md border px-2 py-0.5 text-xs tabular-nums transition-colors " +
                (value.year === y
                  ? "bg-(--accent)/15 text-(--accent) border-(--accent)/30"
                  : "bg-(--muted) text-(--muted-foreground) border-(--border) hover:border-(--accent)/30")
              }
            >
              {y}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-xs uppercase tracking-wide text-(--muted-foreground) mr-1">Quarter</span>
          {QUARTERS.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQuarter(value.quarter === q ? undefined : q)}
              className={
                "rounded-md border px-2 py-0.5 text-xs transition-colors " +
                (value.quarter === q
                  ? "bg-(--accent)/15 text-(--accent) border-(--accent)/30"
                  : "bg-(--muted) text-(--muted-foreground) border-(--border) hover:border-(--accent)/30")
              }
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {(value.tickers.length > 0 || value.year || value.quarter) && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1 text-xs text-(--muted-foreground)">
          <span>Active filters:</span>
          {value.tickers.map((t) => <Badge key={t} variant="accent">{t}</Badge>)}
          {value.year && <Badge variant="accent">{value.year}</Badge>}
          {value.quarter && <Badge variant="accent">{value.quarter}</Badge>}
        </div>
      )}
    </div>
  );
}
