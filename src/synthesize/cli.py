"""End-to-end ask CLI.

    uv run python -m src.synthesize "How did Apple describe Vision Pro?" --ticker AAPL
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import psycopg
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config import get_settings
from src.retrieve.filters import RetrievalFilters
from src.synthesize.pipeline import ask

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("ask")
def ask_command(
    question: str = typer.Argument(..., help="The user question."),
    ticker: list[str] = typer.Option(
        None, "--ticker", "-t", help="Restrict to one or more tickers (repeatable)."
    ),
    year: Optional[int] = typer.Option(None, "--year"),
    quarter: Optional[str] = typer.Option(None, "--quarter"),
    section: Optional[str] = typer.Option(None, "--section", help="prepared | qa"),
    speaker_role: list[str] = typer.Option(
        None, "--speaker-role", "-r"
    ),
    min_hedging: Optional[float] = typer.Option(None, "--min-hedging"),
    topic: list[str] = typer.Option(None, "--topic"),
    candidate_k: int = typer.Option(50, "--candidate-k"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
) -> None:
    """Retrieve top-K chunks and synthesize a cited answer."""
    _setup_logging()
    settings = get_settings()
    filters = RetrievalFilters(
        tickers=ticker or None,
        year=year,
        quarter=quarter,
        section=section,
        speaker_roles=speaker_role or None,
        min_hedging_score=min_hedging,
        topics=topic or None,
    )

    from anthropic import AsyncAnthropic

    anthropic_client = AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
    )

    async def _run():
        with psycopg.connect(str(settings.postgres_url)) as conn:
            return await ask(
                question=question,
                conn=conn,
                anthropic_client=anthropic_client,
                voyage_api_key=settings.voyage_api_key.get_secret_value(),
                cohere_api_key=settings.cohere_api_key.get_secret_value(),
                filters=filters,
                candidate_k=candidate_k,
                top_k=top_k,
            )

    result = asyncio.run(_run())

    console.print(Panel(f"[bold]Q:[/bold] {result.question}", title="Question"))
    console.print(Panel(result.answer, title=f"Answer ({result.model})", padding=(1, 2)))

    cit_table = Table(title=f"Citations ({len(result.citations)})")
    cit_table.add_column("Ticker")
    cit_table.add_column("Quarter")
    cit_table.add_column("Year")
    cit_table.add_column("Speaker")
    for c in result.citations:
        cit_table.add_row(c.ticker, c.quarter, str(c.year), c.speaker)
    console.print(cit_table)

    chunk_table = Table(title=f"Chunks used ({len(result.chunks_used)})")
    chunk_table.add_column("chunk_id")
    chunk_table.add_column("rerank", justify="right")
    chunk_table.add_column("Call")
    chunk_table.add_column("Speaker (role/section)")
    for c in result.chunks_used:
        chunk_table.add_row(
            str(c.chunk_id),
            f"{c.rerank_score:.3f}",
            f"{c.ticker} {c.quarter} {c.year}",
            f"{c.speaker_name or 'Unknown'} ({c.speaker_role or '-'}/{c.section or '-'})",
        )
    console.print(chunk_table)

    console.print(
        f"[dim]usage: in={result.input_tokens} out={result.output_tokens} "
        f"cost=${result.cost_usd:.4f} latency={result.latency_ms}ms[/dim]"
    )
