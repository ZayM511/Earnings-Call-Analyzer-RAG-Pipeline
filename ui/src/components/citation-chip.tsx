"use client";

import { Building2 } from "lucide-react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { Chunk } from "@/lib/api";

interface Props {
  ticker: string;
  quarter: string;
  year: number;
  speaker: string;
  /** The retrieved chunk this citation maps to, if available. */
  chunk?: Chunk;
}

/**
 * Inline citation rendered next to a factual claim in the answer. Hovering
 * reveals the supporting chunk text. The chip styling intentionally stays
 * understated so the answer prose reads cleanly.
 */
export function CitationChip({ ticker, quarter, year, speaker, chunk }: Props) {
  const label = `${ticker} ${quarter} ${year} · ${speaker.split(" ").slice(-1)[0]}`;

  return (
    <HoverCard openDelay={120} closeDelay={120}>
      <HoverCardTrigger asChild>
        <span
          className="inline-flex items-center gap-1 rounded-md border border-(--border) bg-(--muted)/60 px-1.5 py-0.5 text-xs font-medium text-(--muted-foreground) hover:bg-(--accent)/15 hover:text-(--accent) cursor-help mx-0.5 align-baseline whitespace-nowrap"
          data-testid="citation-chip"
        >
          <Building2 className="size-3" />
          {label}
        </span>
      </HoverCardTrigger>
      <HoverCardContent className="w-96 max-w-[90vw]">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs text-(--muted-foreground)">
            <span className="font-semibold text-(--foreground)">
              {ticker} {quarter} {year}
            </span>
            <span>{speaker}</span>
          </div>
          {chunk ? (
            <>
              <div className="flex flex-wrap gap-1 text-[10px] uppercase tracking-wide text-(--muted-foreground)">
                {chunk.speaker_role && <span>{chunk.speaker_role}</span>}
                {chunk.section && <span>· {chunk.section}</span>}
                {typeof chunk.hedging_score === "number" && (
                  <span className="tabular-nums">
                    · hedging {chunk.hedging_score.toFixed(2)}
                  </span>
                )}
              </div>
              <blockquote className="font-serif text-sm leading-relaxed text-(--foreground) border-l-2 border-(--accent) pl-3">
                {chunk.text.length > 360
                  ? chunk.text.slice(0, 360) + "…"
                  : chunk.text}
              </blockquote>
            </>
          ) : (
            <div className="text-xs italic text-(--muted-foreground)">
              No chunk lookup available for this citation.
            </div>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
