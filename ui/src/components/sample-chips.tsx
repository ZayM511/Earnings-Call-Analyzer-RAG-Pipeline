"use client";

import { ArrowRight } from "lucide-react";

const SAMPLES: { label: string; q: string }[] = [
  {
    label: "Vision Pro adoption on AAPL Q4 2024",
    q: "What did Tim Cook say about Apple Intelligence and Vision Pro on Apple's Q4 2024 call?",
  },
  {
    label: "MSFT AI capex framing over time",
    q: "How did Microsoft's framing of AI capital expenditure evolve from fiscal Q3 2024 through fiscal Q2 2026?",
  },
  {
    label: "Apple vs Google on China risk",
    q: "Compare how Apple and Alphabet talk about China exposure and risk on their 2024 and 2025 earnings calls.",
  },
  {
    label: "Evasive CEO answers in 2024",
    q: "Across all Mag 7 calls from 2024, which CEO responses on forward guidance or AI monetization timelines contained the most hedging language?",
  },
];

interface Props {
  onPick: (q: string) => void;
}

export function SampleChips({ onPick }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs uppercase tracking-wide text-(--muted-foreground)">
        Try a sample question
      </span>
      <div className="flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => onPick(s.q)}
            className="group inline-flex items-center gap-1.5 rounded-md border border-(--border) bg-(--card) px-3 py-1.5 text-sm font-medium text-(--foreground) hover:border-(--accent)/40 hover:bg-(--accent)/10 hover:text-(--accent) transition-colors"
            data-testid="sample-chip"
          >
            {s.label}
            <ArrowRight className="size-3 opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        ))}
      </div>
    </div>
  );
}
