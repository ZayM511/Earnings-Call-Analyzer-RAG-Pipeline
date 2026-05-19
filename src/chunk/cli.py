"""Typer CLI for chunking.

Usage:
    uv run python -m src.chunk all
    uv run python -m src.chunk one --raw data/raw/AAPL_2024_Q4.json
    uv run python -m src.chunk summary
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.chunk.pipeline import chunk_all_in_directory, chunk_call, load_chunked_jsonl

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("all")
def chunk_all(
    raw_dir: Path = typer.Option(Path("data/raw"), "--raw-dir", "-r"),
    out_dir: Path = typer.Option(Path("data/interim"), "--out-dir", "-o"),
    floor: int = typer.Option(200, "--floor", help="Minimum chunk size in tokens."),
    ceiling: int = typer.Option(600, "--ceiling", help="Maximum chunk size in tokens."),
) -> None:
    """Chunk every transcript in `raw_dir`, write JSONL per call to `out_dir`."""
    _setup_logging()
    console.print(f"[bold]Chunking {raw_dir} -> {out_dir}[/bold]")
    summary = chunk_all_in_directory(raw_dir, out_dir, floor=floor, ceiling=ceiling)
    console.print(
        f"[green]Done: {summary['calls_chunked']} calls -> "
        f"{summary['total_chunks']} chunks[/green]"
    )
    _print_distribution(out_dir)


@app.command("one")
def chunk_one(
    raw: Path = typer.Option(..., "--raw", help="Path to a single data/raw/*.json file."),
    out_dir: Path = typer.Option(Path("data/interim"), "--out-dir", "-o"),
    floor: int = typer.Option(200, "--floor"),
    ceiling: int = typer.Option(600, "--ceiling"),
) -> None:
    """Chunk a single transcript JSON; useful for debugging."""
    _setup_logging()
    raw_call = json.loads(raw.read_text(encoding="utf-8"))
    chunks = chunk_call(raw_call, floor=floor, ceiling=ceiling)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{raw.stem}_chunks.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    console.print(
        f"[green]Wrote {len(chunks)} chunks to {out_path}[/green]"
    )


@app.command("summary")
def chunk_summary(
    out_dir: Path = typer.Option(Path("data/interim"), "--out-dir", "-o"),
) -> None:
    """Print chunk distribution across all calls in `out_dir`."""
    _print_distribution(out_dir)


def _print_distribution(out_dir: Path) -> None:
    files = sorted(out_dir.glob("*_chunks.jsonl"))
    if not files:
        console.print(f"[red]No chunk files in {out_dir}[/red]")
        return

    total_chunks = 0
    role_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    ticker_counts: Counter[str] = Counter()
    token_sizes: list[int] = []

    for path in files:
        for c in load_chunked_jsonl(path):
            total_chunks += 1
            role_counts[c["speaker_role"]] += 1
            section_counts[c["section"]] += 1
            ticker_counts[c["ticker"]] += 1
            token_sizes.append(int(c["approx_tokens"]))

    table = Table(title=f"Chunk distribution across {len(files)} calls ({total_chunks} chunks)")
    table.add_column("Field", justify="left")
    table.add_column("Distribution", justify="left")
    table.add_row("Roles", ", ".join(f"{k}={v}" for k, v in role_counts.most_common()))
    table.add_row("Sections", ", ".join(f"{k}={v}" for k, v in section_counts.most_common()))
    table.add_row("Tickers", ", ".join(f"{k}={v}" for k, v in sorted(ticker_counts.items())))
    if token_sizes:
        token_sizes.sort()
        n = len(token_sizes)
        mean = sum(token_sizes) // n
        p50 = token_sizes[n // 2]
        p90 = token_sizes[int(n * 0.90)]
        p99 = token_sizes[int(n * 0.99)]
        table.add_row(
            "Tokens",
            f"min={min(token_sizes)} mean={mean} p50={p50} p90={p90} p99={p99} max={max(token_sizes)}",
        )
    console.print(table)
