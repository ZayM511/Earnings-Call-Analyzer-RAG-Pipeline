import Link from "next/link";
import { AskForm } from "@/components/ask-form";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 min-h-screen bg-(--background)">
      <header className="border-b border-(--border) bg-(--card)/80 backdrop-blur">
        <div className="mx-auto max-w-5xl px-6 py-4 flex flex-wrap items-baseline gap-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="inline-flex size-7 items-center justify-center rounded-md bg-(--accent) text-(--accent-foreground) text-xs font-semibold">
              EC
            </span>
            <span className="text-base font-semibold tracking-tight">Earnings Call Analyzer</span>
          </Link>
          <span className="text-xs text-(--muted-foreground)">
            Mag 7 · 41 calls · 1,097 chunks · Q2 2024 → Q1 2026
          </span>
          <nav className="ml-auto flex items-center gap-3 text-sm">
            <Link
              href="/"
              className="text-(--foreground) hover:text-(--accent) font-medium"
            >
              Ask
            </Link>
            <Link
              href="/compare"
              className="text-(--muted-foreground) hover:text-(--accent)"
            >
              Compare
            </Link>
            <Link
              href="https://github.com/ZayM511/Earnings-Call-Analyzer-RAG-Pipeline"
              className="text-(--muted-foreground) hover:text-(--accent)"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl px-6 py-10 flex flex-col gap-8">
        <section className="space-y-2">
          <h1 className="text-2xl md:text-4xl font-medium tracking-tight">
            Earnings calls are weird. Now they&apos;re searchable.
          </h1>
          <p className="text-(--muted-foreground) max-w-3xl">
            A hybrid-retrieval RAG over Mag 7 quarterly transcripts. Speaker-aware
            chunking, Voyage&apos;s finance-tuned embeddings, Cohere rerank, and
            Claude Opus 4.6 synthesis with inline citations. Try a sample question
            below or paste your own.
          </p>
        </section>

        <AskForm />

        <footer className="border-t border-(--border) pt-6 text-xs text-(--muted-foreground)">
          <p>
            Powered by Postgres + pgvector, Voyage <code className="font-mono">voyage-finance-2</code>,
            Cohere Rerank 3.5, Claude Opus 4.6, and Braintrust evals. See the{" "}
            <Link
              href="https://github.com/ZayM511/Earnings-Call-Analyzer-RAG-Pipeline#readme"
              className="text-(--accent) hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              README
            </Link>{" "}
            for the architecture diagram, eval numbers, and design decisions.
          </p>
        </footer>
      </main>
    </div>
  );
}
