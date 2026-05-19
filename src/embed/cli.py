"""Typer CLI for Phase 7 embedding.

    uv run python -m src.embed all
    uv run python -m src.embed summary

`all` embeds every chunk with NULL embedding. `summary` reports per-table
coverage so you can spot missed rows.
"""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg
import typer
from pgvector.psycopg import register_vector
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.embed.pipeline import embed_pending_chunks

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("all")
def all_(
    model: str = typer.Option("voyage-finance-2", "--model", help="Voyage model name."),
    batch_size: int = typer.Option(128, "--batch-size", "-b"),
) -> None:
    """Embed every chunk with NULL embedding."""
    _setup_logging()
    settings = get_settings()
    console.print(
        f"[bold]Embedding pending chunks with {model} "
        f"(batch_size={batch_size})[/bold]"
    )
    summary = embed_pending_chunks(
        postgres_dsn=str(settings.postgres_url),
        voyage_api_key=settings.voyage_api_key.get_secret_value(),
        model=model,
        batch_size=batch_size,
    )
    console.print(
        f"[green]Done: rows_seen={summary.rows_seen} "
        f"rows_embedded={summary.rows_embedded} "
        f"api_calls={summary.api_calls}[/green]"
    )
    print_db_summary(str(settings.postgres_url))


@app.command("summary")
def summary() -> None:
    """Print embedding coverage from Postgres."""
    settings = get_settings()
    print_db_summary(str(settings.postgres_url))


def print_db_summary(dsn: str) -> None:
    with psycopg.connect(dsn) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FILTER (WHERE embedding IS NULL) AS missing,"
                " COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS present,"
                " COUNT(*) AS total FROM chunks"
            )
            missing, present, total = cur.fetchone()  # type: ignore[misc]

            cur.execute(
                """
                SELECT ticker,
                       COUNT(*) FILTER (WHERE embedding IS NULL) AS missing,
                       COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS present
                FROM chunks
                GROUP BY ticker
                ORDER BY ticker
                """
            )
            per_ticker = cur.fetchall()

            # Verify the HNSW index is healthy
            cur.execute(
                "SELECT indexname FROM pg_indexes WHERE indexname = 'chunks_embedding_idx'"
            )
            idx_exists = cur.fetchone() is not None

    console.print(
        f"[bold]Embedding coverage: present={present}/{total}, missing={missing}, "
        f"HNSW index present={idx_exists}[/bold]"
    )
    t = Table(title="Per-ticker embedding state")
    t.add_column("Ticker")
    t.add_column("Present", justify="right")
    t.add_column("Missing", justify="right")
    for ticker, m, p in per_ticker:
        t.add_row(str(ticker), str(p), str(m))
    console.print(t)
