"""Typer CLI for the ingestion pipeline.

Usage:
    uv run python -m src.ingest all-mag7
    uv run python -m src.ingest one --ticker AAPL --year 2024 --quarter Q4
    uv run python -m src.ingest summary

Run `uv run python -m src.ingest --help` for the full surface.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.ingest.audit import insert_audit_rows
from src.ingest.hf_source import (
    DEFAULT_WINDOW_END,
    DEFAULT_WINDOW_START,
    MAG7_TICKERS,
    filter_mag7_window,
    load_rogersurf_parquet,
    normalize_quarter,
)
from src.ingest.transcript_loaders import save_transcripts

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("all-mag7")
def all_mag7(
    output_dir: Path = typer.Option(
        Path("data/raw"),
        "--output-dir",
        "-o",
        help="Directory to write one JSON per call into.",
    ),
    start_date: str = typer.Option(
        DEFAULT_WINDOW_START,
        "--start",
        help="Inclusive lower bound on call_date (YYYY-MM-DD).",
    ),
    end_date: str = typer.Option(
        DEFAULT_WINDOW_END,
        "--end",
        help="Inclusive upper bound on call_date (YYYY-MM-DD).",
    ),
    skip_audit: bool = typer.Option(
        False,
        "--skip-audit",
        help="Do not write to ingest_audit (use for dry runs without a live DB).",
    ),
) -> None:
    """Fetch every Mag 7 transcript in the window from the Rogersurf parquet."""
    _setup_logging()
    console.print("[bold]Loading Rogersurf parquet from HF Hub...[/bold]")
    df = load_rogersurf_parquet()
    console.print(f"  loaded {len(df):,} rows")

    filtered = filter_mag7_window(df, start_date, end_date)
    console.print(
        f"  filtered to {len(filtered)} Mag 7 calls in [{start_date}, {end_date}]"
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = save_transcripts(filtered, output_dir=output_dir)
    console.print(f"[green]Wrote {len(paths)} transcripts to {output_dir}[/green]")

    if not skip_audit:
        dsn = str(get_settings().postgres_url)
        n = insert_audit_rows(dsn, json_paths=paths)
        console.print(f"  wrote {n} rows to ingest_audit")

    _print_coverage_table(filtered, output_dir)


@app.command("one")
def one(
    ticker: str = typer.Option(..., help="Ticker symbol, e.g. AAPL."),
    year: int = typer.Option(..., help="Earnings fiscal year, e.g. 2024."),
    quarter: str = typer.Option(..., help="Quarter, e.g. Q4 or 4."),
    output_dir: Path = typer.Option(Path("data/raw"), "--output-dir", "-o"),
) -> None:
    """Fetch a single transcript by (ticker, year, quarter)."""
    _setup_logging()
    df = load_rogersurf_parquet()
    q = normalize_quarter(quarter)
    sub = df[
        (df["ticker"].str.upper() == ticker.upper())
        & (df["earnings_year"] == year)
        & (df["quarter"].astype(str).str.upper() == q)
    ]
    if sub.empty:
        console.print(f"[red]No call found for {ticker} {year} {q}[/red]")
        raise typer.Exit(code=1)
    paths = save_transcripts(sub, output_dir=output_dir)
    console.print(f"[green]Wrote {len(paths)} transcript(s) for {ticker} {year} {q}[/green]")


@app.command("summary")
def summary(
    output_dir: Path = typer.Option(Path("data/raw"), "--output-dir", "-o"),
) -> None:
    """Print a coverage table for the on-disk transcripts."""
    files = sorted(output_dir.glob("*.json"))
    table = Table(title=f"Transcripts in {output_dir} ({len(files)} files)")
    table.add_column("Ticker", justify="left")
    table.add_column("Year", justify="right")
    table.add_column("Quarter", justify="left")
    table.add_column("File", justify="left")
    for p in files:
        parts = p.stem.split("_")
        if len(parts) >= 3:
            t, y, q = parts[0], parts[1], parts[2]
            table.add_row(t, y, q, p.name)
    console.print(table)


def _print_coverage_table(df, output_dir: Path) -> None:
    """Show which (ticker, year, quarter) combinations we have."""
    table = Table(title="Ingest coverage")
    table.add_column("Ticker", justify="left")
    table.add_column("Year", justify="right")
    table.add_column("Quarter", justify="left")
    table.add_column("Date", justify="left")
    table.add_column("File exists?", justify="center")
    for _, row in df.iterrows():
        t = str(row["ticker"]).upper()
        y = int(row["earnings_year"])
        q = normalize_quarter(row["quarter"])
        d = str(row["call_date"])
        path = output_dir / f"{t}_{y}_{q}.json"
        table.add_row(t, str(y), q, d, "Yes" if path.exists() else "No")
    console.print(table)
    # Per-ticker count
    counts = (
        df.assign(_t=df["ticker"].str.upper())
        .groupby("_t")
        .size()
        .reindex(MAG7_TICKERS, fill_value=0)
    )
    summary_table = Table(title="Per-ticker count")
    summary_table.add_column("Ticker")
    summary_table.add_column("Count", justify="right")
    for ticker in MAG7_TICKERS:
        summary_table.add_row(ticker, str(int(counts.get(ticker, 0))))
    console.print(summary_table)
