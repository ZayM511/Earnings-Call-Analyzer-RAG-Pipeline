"""Eval runner.

Drives the 30-case suite through the live pipeline, computes scores, and
optionally streams each case to Braintrust for the dashboard. Without
Braintrust the runner still works and prints the same metrics to stdout.

We log per-case rows + a final aggregate. The aggregate is what gets
embedded in the README.
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psycopg

from src.eval.cases import EvalCase, all_cases
from src.eval.scorers import (
    CaseScores,
    llm_judge_answer_quality,
    score_case,
)
from src.retrieve.hybrid import RetrievedChunk, hybrid_retrieve
from src.synthesize.opus_synthesizer import SynthesisResult, synthesize

logger = logging.getLogger(__name__)


@dataclass
class CaseRecord:
    case: EvalCase
    chunks: list[RetrievedChunk]
    result: SynthesisResult
    scores: CaseScores


def _aggregate(records: list[CaseRecord]) -> dict[str, Any]:
    """Compute per-route + overall aggregates over the per-case scores."""
    by_route: dict[str, list[CaseScores]] = defaultdict(list)
    for r in records:
        by_route[r.case.query_type].append(r.scores)

    summary: dict[str, Any] = {"overall": {}, "by_route": {}, "n": len(records)}

    def _mean(values: list[float]) -> float:
        return float(statistics.mean(values)) if values else 0.0

    all_scores = [r.scores for r in records]
    summary["overall"] = {
        "recall_at_5": _mean([s.recall_at_5 for s in all_scores]),
        "mrr": _mean([s.mrr for s in all_scores]),
        "theme_coverage": _mean([s.theme_coverage for s in all_scores]),
        "citation_min_satisfied": _mean([s.citation_min_satisfied for s in all_scores]),
        "llm_judge": _mean([s.llm_judge for s in all_scores if s.llm_judge is not None]),
    }

    for route, scores in by_route.items():
        summary["by_route"][route] = {
            "n": len(scores),
            "recall_at_5": _mean([s.recall_at_5 for s in scores]),
            "mrr": _mean([s.mrr for s in scores]),
            "theme_coverage": _mean([s.theme_coverage for s in scores]),
            "citation_min_satisfied": _mean([s.citation_min_satisfied for s in scores]),
            "llm_judge": _mean([s.llm_judge for s in scores if s.llm_judge is not None]),
        }

    return summary


def _maybe_init_braintrust(experiment_name: str, project: str) -> Any | None:
    """Return a Braintrust experiment handle or None if disabled / unavailable."""
    try:
        import braintrust

        exp = braintrust.init(
            project=project,
            experiment=experiment_name,
            api_key=None,  # picks up BRAINTRUST_API_KEY from env
        )
        logger.info("braintrust: experiment %s/%s ready", project, experiment_name)
        return exp
    except Exception as e:  # pragma: no cover -- braintrust optional
        logger.warning("braintrust unavailable: %s", e)
        return None


async def run_eval(
    *,
    postgres_dsn: str,
    anthropic_api_key: str,
    voyage_api_key: str,
    cohere_api_key: str,
    braintrust_project: str | None = None,
    experiment_name: str = "baseline",
    run_llm_judge: bool = True,
    case_filter: str | None = None,
    output_dir: Path | str = "eval_results",
) -> dict[str, Any]:
    """Execute the eval suite end-to-end and return the aggregate dict."""
    from anthropic import AsyncAnthropic

    anthropic_client = AsyncAnthropic(api_key=anthropic_api_key)
    exp = _maybe_init_braintrust(experiment_name, braintrust_project or "earnings-rag") if braintrust_project else None

    cases = all_cases()
    if case_filter:
        cases = [c for c in cases if c.case_id == case_filter or c.query_type == case_filter]

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    per_case_jsonl = output_dir / f"{experiment_name}_per_case.jsonl"

    records: list[CaseRecord] = []
    with psycopg.connect(postgres_dsn) as conn, per_case_jsonl.open("w", encoding="utf-8") as out:
        for case in cases:
            session_id = f"eval:{experiment_name}:{case.case_id}"
            logger.info("running %s (%s)", case.case_id, case.query_type)

            try:
                chunks = hybrid_retrieve(
                    conn=conn,
                    voyage_api_key=voyage_api_key,
                    cohere_api_key=cohere_api_key,
                    query=case.question,
                    filters=case.expected_filters,
                    candidate_k=50,
                    top_k=10,
                )

                result: SynthesisResult = await synthesize(
                    client=anthropic_client,
                    session_id=session_id,
                    question=case.question,
                    chunks=chunks,
                )

                judge_score: float | None = None
                judge_raw: dict[str, Any] = {}
                if run_llm_judge:
                    try:
                        judge_score, judge_raw = await llm_judge_answer_quality(
                            client=anthropic_client,
                            case=case,
                            result=result,
                        )
                    except Exception as e:  # one-judge failure shouldn't break the run
                        logger.warning("llm judge failed for %s: %s", case.case_id, e)

                scores = score_case(
                    case=case,
                    chunks=chunks,
                    answer=result.answer,
                    citations=result.citations,
                    llm_judge_score=judge_score,
                )
                rec = CaseRecord(case=case, chunks=chunks, result=result, scores=scores)
                records.append(rec)

                # Persist per-case row to disk
                out.write(json.dumps({
                    "case_id": case.case_id,
                    "query_type": case.query_type,
                    "question": case.question,
                    "answer": result.answer,
                    "citations": [asdict(c) for c in result.citations],
                    "chunks_top5": [
                        {"chunk_id": c.chunk_id, "ticker": c.ticker, "quarter": c.quarter,
                         "year": c.year, "speaker": c.speaker_name, "role": c.speaker_role,
                         "section": c.section, "rerank": c.rerank_score}
                        for c in chunks[:5]
                    ],
                    "scores": asdict(scores),
                    "judge_rationale": judge_raw.get("rationale", ""),
                    "usage": {
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "cost_usd": result.cost_usd,
                        "latency_ms": result.latency_ms,
                    },
                }, ensure_ascii=False) + "\n")

                # Stream to Braintrust if enabled
                if exp is not None:
                    try:
                        exp.log(
                            input={"question": case.question, "filters": str(case.expected_filters)},
                            output=result.answer,
                            expected=case.expected_themes,
                            scores={
                                "recall_at_5": scores.recall_at_5,
                                "mrr": scores.mrr,
                                "theme_coverage": scores.theme_coverage,
                                "citation_min": scores.citation_min_satisfied,
                                "llm_judge": scores.llm_judge or 0.0,
                            },
                            metadata={
                                "case_id": case.case_id,
                                "query_type": case.query_type,
                                "difficulty": case.difficulty,
                                "n_chunks_retrieved": len(chunks),
                                "n_citations": len(result.citations),
                                "input_tokens": result.input_tokens,
                                "output_tokens": result.output_tokens,
                                "cost_usd": result.cost_usd,
                                "latency_ms": result.latency_ms,
                            },
                        )
                    except Exception as e:  # pragma: no cover
                        logger.warning("braintrust log failed for %s: %s", case.case_id, e)

                logger.info(
                    "%s: recall@5=%.2f mrr=%.2f themes=%.2f cites=%d judge=%s",
                    case.case_id,
                    scores.recall_at_5,
                    scores.mrr,
                    scores.theme_coverage,
                    len(result.citations),
                    f"{judge_score:.2f}" if judge_score is not None else "—",
                )

            except Exception as e:
                logger.exception("case %s failed: %s", case.case_id, e)

    if exp is not None:
        try:
            exp.flush()
        except Exception:  # pragma: no cover
            pass

    summary = _aggregate(records)
    summary["experiment_name"] = experiment_name
    summary["per_case_path"] = str(per_case_jsonl)
    summary_path = output_dir / f"{experiment_name}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary
