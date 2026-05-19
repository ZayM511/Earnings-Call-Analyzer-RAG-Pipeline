"""Typer CLI for the hybrid retrieval pipeline.

    uv run python -m src.retrieve query "How did Apple frame Vision Pro?"
    uv run python -m src.retrieve query "AI capex" --ticker AAPL --ticker MSFT --top-k 5
    uv run python -m src.retrieve query "hedging on guidance" --section qa --min-hedging 0.5
"""

from __future__ import annotations

import logging
from typing import Optional

import psycopg
import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.retrieve.filters import RetrievalFilters
from src.retrieve.hybrid import hybrid_retrieve

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("query")
def query(
    text: str = typer.Argument(..., help="The user question."),
    ticker: list[str] = typer.Option(
        None, "--ticker", "-t", help="Restrict to one or more tickers (repeatable)."
    ),
    year: Optional[int] = typer.Option(None, "--year"),
    quarter: Optional[str] = typer.Option(None, "--quarter", help="e.g. Q3"),
    section: Optional[str] = typer.Option(None, "--section", help="prepared | qa"),
    speaker_role: list[str] = typer.Option(
        None, "--speaker-role", "-r", help="CEO, CFO, Analyst, Operator, IR, Other (repeatable)"
    ),
    min_hedging: Optional[float] = typer.Option(
        None, "--min-hedging", help="Floor on hedging_score in [0, 1]."
    ),
    topic: list[str] = typer.Option(
        None, "--topic", help="Restrict to chunks tagged with at least one of these topics."
    ),
    candidate_k: int = typer.Option(50, "--candidate-k"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
) -> None:
    """Run the hybrid pipeline for one question and print the top-K chunks."""
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
    console.print(f"[bold]Query:[/bold] {text}")
    if any([ticker, year, quarter, section, speaker_role, min_hedging, topic]):
        console.print(f"[dim]Filters:[/dim] {filters}")

    with psycopg.connect(str(settings.postgres_url)) as conn:
        chunks = hybrid_retrieve(
            conn=conn,
            voyage_api_key=settings.voyage_api_key.get_secret_value(),
            cohere_api_key=settings.cohere_api_key.get_secret_value(),
            query=text,
            filters=filters,
            candidate_k=candidate_k,
            top_k=top_k,
        )

    if not chunks:
        console.print("[red]No results.[/red]")
        raise typer.Exit(code=0)

    table = Table(title=f"Top {len(chunks)} reranked chunks", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("rerank", justify="right")
    table.add_column("ticker")
    table.add_column("quarter")
    table.add_column("role")
    table.add_column("section")
    table.add_column("speaker")
    table.add_column("text", overflow="fold", max_width=80)

    for i, c in enumerate(chunks, start=1):
        table.add_row(
            str(i),
            f"{c.rerank_score:.3f}",
            c.ticker,
            f"{c.quarter} {c.year}",
            c.speaker_role or "—",
            c.section or "—",
            (c.speaker_name or "Unknown")[:24],
            c.text[:180] + ("…" if len(c.text) > 180 else ""),
        )
    console.print(table)
