# Frontend Design — Aesthetic and Stack

This skill is the design north star for the UI. Claude Code consults it whenever it touches frontend code. The point is to keep the visual style coherent and to avoid the generic AI-product aesthetic.

## The stack (committed)

- **Framework:** Next.js 15 with the App Router.
- **CSS:** Tailwind CSS (mobile-first by default).
- **Components:** shadcn/ui v4 (copy-pasteable Radix + Tailwind primitives — you own the code).
- **Motion:** Framer Motion. Sprinkle, don't drench.
- **Charts:** Recharts for line, bar, radar (tone-over-time, hedging-score-over-time). Visx + d3 reserved for any bespoke visualization that emerges.
- **Icons:** Lucide React (ships with shadcn).
- **Fonts:** Geist Sans for UI and body. Newsreader (a real serif) for long-form quote text inside the citation hover cards.

## What "great" looks like for this project

A recruiter scrolling on their phone gets the point in 30 seconds. They open the laptop, hit the demo URL, and the desktop layout makes them stop scrolling. The citation chips on every claim and the Q&A evasion classifier are the killer features — they see the system's grounded reasoning.

The aesthetic is finance-precise: tight type, generous whitespace, one accent color used sparingly, fast quiet transitions. Not "AI-flashy." Not "designer-portfolio fancy." Production-app polished.

## Color tokens

- Background dark: `#0f0f10` (warm dark, not pure black).
- Background light: `#fafaf7` (off-white).
- Foreground dark on light: `#171717`.
- Foreground light on dark: `#f5f5f5`.
- Accent: one color used for the active-mode toggle, the focus ring, and the hedging-heatmap saturated end. Pick once and stick to it. Suggestion: a muted ledger green `#16a34a` at 60% saturation for dark mode, slightly deeper for light.
- Hedging-score color scale (heatmap): five-step ramp from cool blue (`hedging_score ≈ 0.0`, confident) to warm red (`hedging_score ≈ 1.0`, evasive). Use the d3-scale-chromatic `interpolateRdYlBu` reversed.
- Sentiment color: green for positive, neutral gray for neutral, dim red for negative. Subtle — only used as a left-border accent on chunk cards, not a fill.

## Type scale (responsive)

```jsx
// hero
<h1 className="text-2xl md:text-4xl lg:text-5xl tracking-tight font-medium">

// section
<h2 className="text-xl md:text-2xl tracking-tight">

// body
<p className="text-sm md:text-base leading-relaxed">

// pull-quote (citation hover content)
<blockquote className="font-serif text-base leading-relaxed">

// numbers (hedging score, sentiment counts, etc.)
<span className="font-mono tabular-nums">0.74</span>
```

Always use `tabular-nums` for any number that might appear next to another number. Without it, "0.74" and "0.81" don't line up.

## Motion rules

- **Never longer than 250ms.** Anything longer feels slow.
- **Spring, not ease.** Framer Motion's `spring` physics feel native; CSS `ease-out` feels generic.
- **Respect `prefers-reduced-motion`.** Wrap motion in a `useReducedMotion()` check; fall back to instant.
- **One motion per interaction.** Layering "fade in + slide up + scale" reads as fussy. Pick the most meaningful one.

```jsx
import { motion, useReducedMotion } from "framer-motion"

const reduce = useReducedMotion()
<motion.div
  initial={reduce ? false : { opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ type: "spring", stiffness: 350, damping: 30 }}
/>
```

## Project-specific component patterns

### Citation chip

Inline chip on every cited claim. Shows ticker + quarter + year + speaker. Hover reveals the exact quoted text (shadcn `HoverCard`).

```jsx
<HoverCard>
  <HoverCardTrigger asChild>
    <span className="inline-flex items-center gap-1 rounded-md border bg-muted/40 px-1.5 py-0.5 text-xs">
      <Building2 className="size-3" />
      AAPL Q3 2024 · Tim Cook
    </span>
  </HoverCardTrigger>
  <HoverCardContent className="max-w-md font-serif text-sm leading-relaxed">
    {quote}
  </HoverCardContent>
</HoverCard>
```

### Mode toggle (Single-call vs Cross-company)

Two-segment toggle at the top of the chat panel. shadcn `ToggleGroup`. Active state uses the accent color.

### Hedging heatmap (the demo killer for Q&A)

Two-column layout. Left column: every analyst question for a given call. Right column: the exec's answer. Each row's background gradient is driven by the answer's `hedging_score`: cool blue at 0.0, warm red at 1.0. Click a row to see the full quote.

```jsx
<div
  className="rounded-md p-3"
  style={{
    background: `linear-gradient(90deg, transparent, ${heatmapColor(answer.hedging_score)} 80%)`,
  }}
>
  <div className="text-sm font-medium">{question}</div>
  <div className="mt-1 text-sm text-muted-foreground">{answer.text}</div>
  <div className="mt-1 text-xs tabular-nums">hedging {answer.hedging_score.toFixed(2)}</div>
</div>
```

### Tone-over-time chart per executive

Recharts `LineChart` with 8 quarters on the x-axis, two lines: `hedging_score` average and `sentiment` (mapped 1 / 0 / -1 then averaged). Hovering a point shows the call link.

### Side-by-side multi-company comparison

Three-column grid (desktop) or stacked accordion (mobile). One synthesis call per column, all answering the same question, citations shown inline. shadcn `Card` per column with a `Badge` for the ticker.

### Empty states

Specific copy. Never "No data."

- Chat empty: "Ask anything about the Mag 7's earnings calls from Q2 2024 to Q1 2026. Try: *Where did Tesla execs start hedging on forward guidance?*"
- Search empty: "I couldn't find that. Try widening the ticker filter or paraphrasing."

### Loading states

Specific. "Searching 56 calls, 6,300 chunks…" beats a spinner alone. "Asking Opus to synthesize…" beats "Loading…"

## Anti-patterns

- **Pure black backgrounds.** Use `#0f0f10`. Pure black bleeds into device bezels and looks dead.
- **Five colors of equal weight.** Pick one accent. Everything else is neutral.
- **Bouncy spring physics on every interaction.** Reads as toy. Save the bounce for one or two delightful moments.
- **Animating longer than 250ms.** Slow.
- **`text-justify` on any body text.** River-of-rivers effect. Use `text-left`.
- **Inter for body text.** Overused. Geist Sans is a better default in 2026.
- **Square cards with no hover state.** Add at least a `hover:bg-muted/60` so things feel alive.
- **Skipping `useReducedMotion`.** Accessibility regression.

## When to reach for the shadcn MCP server

When implementing a new component, run the shadcn MCP server's `list` / `search` first. It exposes shadcn/ui v4 components by natural-language prompt ("install HoverCard", "show me dashboard blocks", "find a layout with a chat panel and a sidebar"). Beats copy-pasting from web docs.

Set `GITHUB_PERSONAL_ACCESS_TOKEN` to lift the rate limit from 60/hour to 5000/hour. No scopes required.

## The interview line

"I used Next.js with shadcn/ui and Tailwind because that is the modern AI-product default and lets me focus engineering effort on the interesting parts — the citation chips, the hedging heatmap, the side-by-side multi-company comparison. The boring foundation frees up budget for the parts that demonstrate the actual work."
