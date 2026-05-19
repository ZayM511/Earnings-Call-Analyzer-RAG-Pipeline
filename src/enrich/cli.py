"""Typer CLI for the enrichment phase.

Usage:
    uv run python -m src.enrich all
    uv run python -m src.enrich one --raw data/interim/AAPL_2024_Q4_chunks.jsonl
    uv run python -m src.enrich summary

`all` runs the full pipeline against Anthropic. `one` runs against a single
call's JSONL (useful for debugging cost/calibration). `summary` queries
Postgres for distribution metrics.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import psycopg
import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.enrich.pipeline import enrich_all, write_summary_jsonl

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("all")
def all_(
    interim_dir: Path = typer.Option(Path("data/interim"), "--interim-dir", "-i"),
    summary_path: Path = typer.Option(
        Path("eval_results/enrichment_summary.json"),
        "--summary-path",
    ),
    concurrency: int = typer.Option(8, "--concurrency", "-c"),
) -> None:
    """Enrich every chunked transcript via Claude Sonnet 4.5 and write to Postgres."""
    _setup_logging()
    settings = get_settings()
    console.print(
        f"[bold]Enriching {interim_dir} -> Postgres "
        f"(concurrency={concurrency}, project={settings.braintrust_project})[/bold]"
    )

    summary = asyncio.run(
        enrich_all(
            interim_dir=interim_dir,
            postgres_dsn=str(settings.postgres_url),
            anthropic_api_key=settings.anthropic_api_key.get_secret_value(),
            concurrency=concurrency,
        )
    )
    write_summary_jsonl(summary_path, summary)

    console.print(
        f"[green]Done: seen={summary.chunks_seen} "
        f"enriched={summary.chunks_enriched} "
        f"persisted={summary.chunks_persisted} "
        f"failed={summary.chunks_failed}[/green]"
    )
    if summary.failed_chunks:
        console.print(f"[yellow]Failed: {summary.failed_chunks[:10]}...[/yellow]")

    print_db_summary(str(settings.postgres_url))


@app.command("one")
def one(
    raw: Path = typer.Option(..., "--raw", help="A single data/interim/*_chunks.jsonl"),
    concurrency: int = typer.Option(4, "--concurrency", "-c"),
) -> None:
    """Enrich one call's chunks. Useful for debugging without billing the full corpus."""
    _setup_logging()
    settings = get_settings()
    # Temporarily symlink/copy to a temp dir so enrich_all sees one file.
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        shutil.copy(raw, td_path / raw.name)
        summary = asyncio.run(
            enrich_all(
                interim_dir=td_path,
                postgres_dsn=str(settings.postgres_url),
                anthropic_api_key=settings.anthropic_api_key.get_secret_value(),
                concurrency=concurrency,
            )
        )
        console.print(
            f"[green]Done: enriched={summary.chunks_enriched} "
            f"persisted={summary.chunks_persisted} failed={summary.chunks_failed}[/green]"
        )


@app.command("summary")
def summary() -> None:
    """Print distribution metrics from the chunks table."""
    settings = get_settings()
    print_db_summary(str(settings.postgres_url))


def print_db_summary(dsn: str) -> None:
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM chunks")
        total = int(cur.fetchone()[0])  # type: ignore[index]

        cur.execute(
            """
            SELECT section,
                   ROUND(AVG(hedging_score)::numeric, 3) AS avg_hedge,
                   COUNT(*) AS n
            FROM chunks
            WHERE hedging_score IS NOT NULL
            GROUP BY section
            ORDER BY section
            """
        )
        section_rows = cur.fetchall()

        cur.execute(
            """
            SELECT speaker_role,
                   COUNT(*) AS n,
                   ROUND(AVG(hedging_score)::numeric, 3) AS avg_hedge
            FROM chunks
            GROUP BY speaker_role
            ORDER BY n DESC
            """
        )
        role_rows = cur.fetchall()

        cur.execute(
            """
            SELECT sentiment,
                   COUNT(*) AS n
            FROM chunks
            GROUP BY sentiment
            ORDER BY n DESC
            """
        )
        sent_rows = cur.fetchall()

        cur.execute(
            """
            SELECT topic, COUNT(*) AS n
            FROM (SELECT UNNEST(topics) AS topic FROM chunks WHERE topics IS NOT NULL) t
            GROUP BY topic
            ORDER BY n DESC
            LIMIT 20
            """
        )
        topic_rows = cur.fetchall()

    console.print(f"[bold]Total chunks in DB: {total}[/bold]")

    t1 = Table(title="Avg hedging by section")
    t1.add_column("section"); t1.add_column("avg_hedge", justify="right"); t1.add_column("n", justify="right")
    for r in section_rows:
        t1.add_row(str(r[0]), str(r[1]), str(r[2]))
    console.print(t1)

    t2 = Table(title="Chunks by role")
    t2.add_column("role"); t2.add_column("n", justify="right"); t2.add_column("avg_hedge", justify="right")
    for r in role_rows:
        t2.add_row(str(r[0]), str(r[1]), str(r[2]))
    console.print(t2)

    t3 = Table(title="Sentiment distribution")
    t3.add_column("sentiment"); t3.add_column("n", justify="right")
    for r in sent_rows:
        t3.add_row(str(r[0]), str(r[1]))
    console.print(t3)

    t4 = Table(title="Top 20 topics")
    t4.add_column("topic"); t4.add_column("n", justify="right")
    for r in topic_rows:
        t4.add_row(str(r[0]), str(r[1]))
    console.print(t4)
