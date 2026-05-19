"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import { CitationChip } from "@/components/citation-chip";
import type { AskResponse, Chunk } from "@/lib/api";

interface Props {
  result: AskResponse;
}

// Match [TICKER QQ YYYY, Speaker Name] inline citations the synthesizer emits.
const CITATION_RE = /\[([A-Z]{1,5})\s+(Q[1-4])\s+(\d{4})\s*,\s*([^\]\[]+?)\]/g;

/**
 * Renders the synthesis answer as Markdown but splices our `<CitationChip>`
 * in place of every `[TICKER QQ YYYY, Speaker]` bracket. The chip's hover
 * card shows the supporting chunk on hover.
 */
export function AnswerView({ result }: Props) {
  // Build a quick lookup from (ticker, quarter, year, speaker-last-name) to chunk.
  const chunkByKey = React.useMemo(() => {
    const map = new Map<string, Chunk>();
    for (const c of result.chunks) {
      if (!c.speaker_name) continue;
      const lastName = c.speaker_name.split(" ").slice(-1)[0];
      map.set(`${c.ticker}|${c.quarter}|${c.year}|${lastName}`, c);
      // Also key by full speaker so we hit on either match.
      map.set(`${c.ticker}|${c.quarter}|${c.year}|${c.speaker_name}`, c);
    }
    return map;
  }, [result]);

  const findChunk = React.useCallback(
    (ticker: string, quarter: string, year: number, speaker: string): Chunk | undefined => {
      const lastName = speaker.split(" ").slice(-1)[0];
      return (
        chunkByKey.get(`${ticker}|${quarter}|${year}|${speaker}`) ||
        chunkByKey.get(`${ticker}|${quarter}|${year}|${lastName}`)
      );
    },
    [chunkByKey],
  );

  // Replace bracket citations with sentinel tokens, then post-process during render.
  // react-markdown doesn't expose a clean "splice components into a text node" API,
  // so we render Markdown then mutate the textual children. To keep this simple
  // and reliable, we pre-render the answer text with a custom paragraph component
  // that replaces matched citations with <CitationChip>.

  const renderTextWithChips = React.useCallback(
    (text: string): React.ReactNode[] => {
      const nodes: React.ReactNode[] = [];
      let lastIndex = 0;
      CITATION_RE.lastIndex = 0;
      let m: RegExpExecArray | null;
      while ((m = CITATION_RE.exec(text)) !== null) {
        const [full, ticker, quarter, yearStr, speakerRaw] = m;
        const start = m.index;
        if (start > lastIndex) nodes.push(text.slice(lastIndex, start));
        const year = parseInt(yearStr, 10);
        const speaker = speakerRaw.trim();
        nodes.push(
          <CitationChip
            key={`${start}-${full}`}
            ticker={ticker}
            quarter={quarter}
            year={year}
            speaker={speaker}
            chunk={findChunk(ticker, quarter, year, speaker)}
          />,
        );
        lastIndex = start + full.length;
      }
      if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
      return nodes;
    },
    [findChunk],
  );

  return (
    <div className="prose prose-sm md:prose-base max-w-none text-(--foreground)">
      <ReactMarkdown
        components={{
          // Inline elements that may contain citation strings inside their text.
          p: ({ children }) => (
            <p className="leading-relaxed">{renderChildren(children, renderTextWithChips)}</p>
          ),
          li: ({ children }) => (
            <li>{renderChildren(children, renderTextWithChips)}</li>
          ),
          h1: ({ children }) => <h2 className="text-xl font-semibold tracking-tight mt-4 mb-2">{renderChildren(children, renderTextWithChips)}</h2>,
          h2: ({ children }) => <h3 className="text-lg font-semibold tracking-tight mt-4 mb-2">{renderChildren(children, renderTextWithChips)}</h3>,
          h3: ({ children }) => <h4 className="text-base font-semibold tracking-tight mt-3 mb-2">{renderChildren(children, renderTextWithChips)}</h4>,
          strong: ({ children }) => <strong>{renderChildren(children, renderTextWithChips)}</strong>,
          em: ({ children }) => <em>{renderChildren(children, renderTextWithChips)}</em>,
          a: ({ children, ...props }) => (
            <a className="text-(--accent) underline" {...props}>
              {renderChildren(children, renderTextWithChips)}
            </a>
          ),
        }}
      >
        {result.answer}
      </ReactMarkdown>
    </div>
  );
}

/** Walk react-markdown's children, splicing chips into every plain-text leaf. */
function renderChildren(
  children: React.ReactNode,
  render: (s: string) => React.ReactNode[],
): React.ReactNode {
  return React.Children.map(children, (child) => {
    if (typeof child === "string") return render(child);
    return child;
  });
}
