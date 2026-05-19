"""Reciprocal Rank Fusion (RRF).

Merge ranked lists from BM25 + dense vector search into a single ranking:

    score(d) = sum over rankings r of 1 / (k + rank_r(d))

where rank_r is 1-indexed. `k=60` is the standard published default; lower
k weights early-rank slots more aggressively. The function is order-stable
on ties (the document that came first in the first ranking wins).

Reference: Cormack et al., "Reciprocal Rank Fusion outperforms Condorcet
and individual Rank Learning Methods" (SIGIR 2009).
"""

from __future__ import annotations

from collections import OrderedDict


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    *,
    k: int = 60,
) -> list[tuple[int, float]]:
    """Merge `rankings` into a single ordered `(doc_id, score)` list.

    Args:
        rankings: list of ranked doc_id lists (highest-rank first within each).
        k: smoothing constant; standard value is 60.

    Returns:
        List of `(doc_id, score)` sorted by score descending.
    """
    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    scored: dict[int, float] = OrderedDict()
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scored[doc_id] = scored.get(doc_id, 0.0) + 1.0 / (k + rank)

    # `sorted` is stable, so docs with equal scores retain their first-seen order.
    return sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
