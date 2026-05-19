"""Eval CLI.

    uv run python -m src.eval baseline
    uv run python -m src.eval baseline --no-judge      # skip the expensive LLM grader
    uv run python -m src.eval baseline --case sc01_aapl_q4_2024_apple_intelligence
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.eval.runner import run_eval

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@app.command("rerank-ablation")
def rerank_ablation_cmd(
    output_path: Path = typer.Option(
        Path("eval_results/experiment_rerank.json"), "--output-path"
    ),
) -> None:
    """A/B experiment: with vs without Cohere Rerank 3.5 across the 30 cases."""
    _setup_logging()
    settings = get_settings()
    from src.eval.experiments import run_rerank_ablation

    summary = run_rerank_ablation(
        postgres_dsn=str(settings.postgres_url),
        voyage_api_key=settings.voyage_api_key.get_secret_value(),
        cohere_api_key=settings.cohere_api_key.get_secret_value(),
        output_path=output_path,
    )
    _print_experiment_summary(summary)


@app.command("hedging-filter-ablation")
def hedging_filter_ablation_cmd(
    output_path: Path = typer.Option(
        Path("eval_results/experiment_hedging_filter.json"), "--output-path"
    ),
) -> None:
    """A/B experiment: with vs without the min_hedging_score pre-filter."""
    _setup_logging()
    settings = get_settings()
    from src.eval.experiments import run_hedging_filter_ablation

    summary = run_hedging_filter_ablation(
        postgres_dsn=str(settings.postgres_url),
        voyage_api_key=settings.voyage_api_key.get_secret_value(),
        cohere_api_key=settings.cohere_api_key.get_secret_value(),
        output_path=output_path,
    )
    _print_experiment_summary(summary)


def _print_experiment_summary(summary: dict) -> None:
    console.print(f"\n[bold]{summary['name']}[/bold]")
    t = Table()
    t.add_column("variant")
    t.add_column("n", justify="right")
    t.add_column("recall@5", justify="right")
    t.add_column("MRR", justify="right")
    for variant, m in summary["summary"].items():
        t.add_row(
            variant,
            str(m["n"]),
            f"{m['recall_at_5']:.3f}",
            f"{m['mrr']:.3f}",
        )
    console.print(t)


@app.command("baseline")
def baseline(
    experiment_name: str = typer.Option("baseline", "--name"),
    no_judge: bool = typer.Option(False, "--no-judge", help="Skip the LLM-as-judge scorer."),
    case: str = typer.Option(None, "--case", help="Run a single case or single query_type."),
    output_dir: Path = typer.Option(Path("eval_results"), "--output-dir", "-o"),
    no_braintrust: bool = typer.Option(False, "--no-braintrust"),
) -> None:
    """Run the baseline 30-case eval suite and print + persist aggregate metrics."""
    _setup_logging()
    settings = get_settings()
    console.print(f"[bold]Running eval: {experiment_name}[/bold]")
    summary = asyncio.run(
        run_eval(
            postgres_dsn=str(settings.postgres_url),
            anthropic_api_key=settings.anthropic_api_key.get_secret_value(),
            voyage_api_key=settings.voyage_api_key.get_secret_value(),
            cohere_api_key=settings.cohere_api_key.get_secret_value(),
            braintrust_project=None if no_braintrust else settings.braintrust_project,
            experiment_name=experiment_name,
            run_llm_judge=not no_judge,
            case_filter=case,
            output_dir=output_dir,
        )
    )
    _print_summary(summary)


def _print_summary(summary: dict) -> None:
    overall = summary["overall"]
    console.print(f"\n[bold]Overall (n={summary['n']})[/bold]")
    t = Table()
    t.add_column("metric")
    t.add_column("value", justify="right")
    for k, v in overall.items():
        t.add_row(k, f"{v:.3f}" if isinstance(v, float) else str(v))
    console.print(t)

    for route, m in summary["by_route"].items():
        console.print(f"\n[bold]{route} (n={m['n']})[/bold]")
        t = Table()
        t.add_column("metric")
        t.add_column("value", justify="right")
        for k, v in m.items():
            if k == "n":
                continue
            t.add_row(k, f"{v:.3f}" if isinstance(v, float) else str(v))
        console.print(t)

    console.print(f"\n[dim]per-case rows: {summary.get('per_case_path')}[/dim]")
    console.print(f"[dim]summary: {summary.get('summary_path')}[/dim]")
