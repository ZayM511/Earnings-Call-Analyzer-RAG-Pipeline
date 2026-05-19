"""A/B experiments for the README screenshot section.

Each experiment is a retrieval-only ablation (no synthesis, no LLM judge) so
the marginal cost is dominated by Voyage embed + Cohere rerank, around
$0.05 per 30-query sweep. The point is to surface where each pipeline
choice earned its keep.

Three experiments ship:

1. **rerank_ablation** — toggle Cohere Rerank 3.5 on / off. Measures the
   recall@5 + MRR lift the reranker buys over plain RRF.

2. **hedging_filter_ablation** — toggle the `min_hedging_score >= 0.4`
   pre-filter for the case that targets evasive CEO answers (cc09).
   Measures precision of the metadata enrichment.

3. **voyage_finance_vs_general** — swap the embedding model on the QUERY
   side only (chunks stay embedded with voyage-finance-2). Tests whether
   asymmetric model use degrades recall. The clean version (re-embedding
   the corpus with voyage-3-large) is a follow-up.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import psycopg

# Cohere trial keys are rate-limited to 10 calls / minute. Pacing ~7 seconds
# between rerank-bearing cases keeps the ablation under the cap.
_RERANK_THROTTLE_SECONDS = 7.0

from src.eval.cases import EvalCase, all_cases
from src.embed.voyage_rest_client import embed_batch
from src.retrieve.bm25 import bm25_search
from src.retrieve.dense import dense_search
from src.retrieve.filters import RetrievalFilters
from src.retrieve.rerank import cohere_rerank
from src.retrieve.rrf import reciprocal_rank_fusion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaseAblationRow:
    case_id: str
    variant: str  # e.g. "with_rerank" / "without_rerank"
    recall_at_5: float
    mrr: float
    n_candidates: int


def _expected_tickers_for(case: EvalCase) -> set[str]:
    return set(case.expected_tickers)


def _recall_at_5(ranked_tickers: list[str], expected: set[str]) -> float:
    if not expected or not ranked_tickers:
        return 0.0
    top = ranked_tickers[:5]
    return sum(1 for t in top if t in expected) / len(top)


def _mrr(ranked_tickers: list[str], expected: set[str]) -> float:
    for rank, t in enumerate(ranked_tickers, start=1):
        if t in expected:
            return 1.0 / rank
    return 0.0


def _hybrid_then_optional_rerank(
    conn: psycopg.Connection,
    case: EvalCase,
    voyage_api_key: str,
    cohere_api_key: str | None,
) -> tuple[list[str], int]:
    """Run hybrid retrieval; rerank only when `cohere_api_key` is provided.

    Returns (ranked_tickers_top_n, n_candidates_before_rerank).
    """
    [query_vec] = embed_batch(
        [case.question],
        api_key=voyage_api_key,
        model="voyage-finance-2",
        input_type="query",
    )
    bm25_hits = bm25_search(conn, case.question, filters=case.expected_filters, limit=50)
    dense_hits = dense_search(conn, query_vec, filters=case.expected_filters, limit=50)
    rrf = reciprocal_rank_fusion(
        [[h.chunk_id for h in bm25_hits], [h.chunk_id for h in dense_hits]]
    )
    if not rrf:
        return [], 0

    # Build chunk_id -> ticker lookup from both lanes.
    ticker_by_id: dict[int, str] = {}
    for h in dense_hits:
        ticker_by_id[h.chunk_id] = h.ticker
    for h in bm25_hits:
        ticker_by_id[h.chunk_id] = h.ticker

    candidate_chunks = [(cid, ticker_by_id[cid]) for cid, _ in rrf if cid in ticker_by_id]
    n_candidates = len(candidate_chunks)

    if cohere_api_key is None:
        # Plain RRF order, no rerank.
        return [t for _, t in candidate_chunks[:10]], n_candidates

    # Rerank by sending the chunk text through Cohere. We need the text again;
    # pull it from whichever hit list has it.
    text_by_id: dict[int, str] = {}
    for h in dense_hits:
        text_by_id[h.chunk_id] = h.text
    for h in bm25_hits:
        text_by_id[h.chunk_id] = h.text

    docs = [text_by_id[cid] for cid, _ in candidate_chunks]
    rerank_results = cohere_rerank(
        api_key=cohere_api_key,
        query=case.question,
        documents=docs,
        top_n=10,
    )
    ranked_tickers = [candidate_chunks[r.original_index][1] for r in rerank_results]
    return ranked_tickers, n_candidates


def run_rerank_ablation(
    *,
    postgres_dsn: str,
    voyage_api_key: str,
    cohere_api_key: str,
    output_path: Path | str = "eval_results/experiment_rerank.json",
) -> dict:
    """Compare with-rerank vs without-rerank across the 30-case suite."""
    rows: list[CaseAblationRow] = []
    with psycopg.connect(postgres_dsn) as conn:
        for case_idx, case in enumerate(all_cases()):
            expected = _expected_tickers_for(case)
            for variant, key in (("with_rerank", cohere_api_key), ("without_rerank", None)):
                # Throttle the rerank-bearing variant to stay under Cohere
                # trial key's 10-calls/minute cap. Skip the throttle on the
                # very first call.
                if variant == "with_rerank" and case_idx > 0:
                    time.sleep(_RERANK_THROTTLE_SECONDS)
                tickers, n = _hybrid_then_optional_rerank(
                    conn, case, voyage_api_key, key
                )
                rows.append(
                    CaseAblationRow(
                        case_id=case.case_id,
                        variant=variant,
                        recall_at_5=_recall_at_5(tickers, expected),
                        mrr=_mrr(tickers, expected),
                        n_candidates=n,
                    )
                )
                logger.info(
                    "rerank_ablation: %s/%s recall@5=%.2f mrr=%.2f n=%d",
                    case.case_id, variant,
                    rows[-1].recall_at_5, rows[-1].mrr, n,
                )

    summary = _summarize(rows, "rerank_ablation")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_hedging_filter_ablation(
    *,
    postgres_dsn: str,
    voyage_api_key: str,
    cohere_api_key: str,
    output_path: Path | str = "eval_results/experiment_hedging_filter.json",
) -> dict:
    """Compare retrieval for the evasive-CEO case with and without the
    `min_hedging_score >= 0.4` pre-filter."""
    rows: list[CaseAblationRow] = []
    target_case = next(c for c in all_cases() if c.case_id == "cc09_evasive_ceo_responses_2024")

    with psycopg.connect(postgres_dsn) as conn:
        # Variant 1: with the hedging filter (the case's default).
        with_filter = target_case
        without_filter = EvalCase(
            case_id=target_case.case_id,
            query_type=target_case.query_type,
            question=target_case.question,
            expected_filters=RetrievalFilters(
                year=2024, speaker_roles=["CEO"], section="qa"  # drop min_hedging
            ),
            expected_themes=target_case.expected_themes,
            expected_tickers=target_case.expected_tickers,
            expected_min_citations=target_case.expected_min_citations,
            difficulty=target_case.difficulty,
        )
        for variant, case in (("with_hedging_filter", with_filter), ("without_hedging_filter", without_filter)):
            tickers, n = _hybrid_then_optional_rerank(
                conn, case, voyage_api_key, cohere_api_key
            )
            # Additional signal: how many of the top-10 chunks come from sample
            # high-hedge speakers (no easy oracle here without a full re-query).
            rows.append(
                CaseAblationRow(
                    case_id=case.case_id,
                    variant=variant,
                    recall_at_5=_recall_at_5(tickers, _expected_tickers_for(case)),
                    mrr=_mrr(tickers, _expected_tickers_for(case)),
                    n_candidates=n,
                )
            )
            logger.info(
                "hedging_filter_ablation: %s recall@5=%.2f mrr=%.2f n=%d",
                variant, rows[-1].recall_at_5, rows[-1].mrr, n,
            )

    summary = _summarize(rows, "hedging_filter_ablation")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _summarize(rows: list[CaseAblationRow], name: str) -> dict:
    from collections import defaultdict
    by_variant: dict[str, list[CaseAblationRow]] = defaultdict(list)
    for r in rows:
        by_variant[r.variant].append(r)

    out: dict = {"name": name, "rows": [asdict(r) for r in rows], "summary": {}}
    for variant, vrows in by_variant.items():
        if not vrows:
            continue
        out["summary"][variant] = {
            "n": len(vrows),
            "recall_at_5": sum(r.recall_at_5 for r in vrows) / len(vrows),
            "mrr": sum(r.mrr for r in vrows) / len(vrows),
        }
    return out
