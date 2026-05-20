import Link from "next/link";
import { AskForm } from "@/components/ask-form";
import { SiteHeader } from "@/components/site-header";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 min-h-screen bg-(--background)">
      <SiteHeader />

      <main className="mx-auto w-full max-w-5xl px-6 py-10 flex flex-col gap-8">
        <section className="space-y-2">
          <h1 className="hero-headline text-2xl md:text-4xl font-medium tracking-tight">
            Earnings calls are weird. Now they&apos;re searchable.
          </h1>
          <p className="text-(--muted-foreground) max-w-3xl leading-relaxed">
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
            Cohere Rerank 3.5, Claude Opus 4.6, and Braintrust evals. See{" "}
            <Link
              href="/how-i-made-this"
              className="text-(--accent) hover:underline"
            >
              How I Made This
            </Link>{" "}
            for the architecture diagram, design decisions, and eval numbers.
          </p>
        </footer>
      </main>
    </div>
  );
}
