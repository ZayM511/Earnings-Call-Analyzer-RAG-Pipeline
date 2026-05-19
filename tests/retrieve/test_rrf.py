"""Tests for src/retrieve/rrf.py.

Reciprocal Rank Fusion: score(d) = sum_r 1 / (k + rank_r(d)) across input
rankings r. Pure function; entirely TDDable.
"""

from __future__ import annotations

import pytest

from src.retrieve.rrf import reciprocal_rank_fusion


def test_empty_rankings_returns_empty_list() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_single_ranking_preserves_order() -> None:
    out = reciprocal_rank_fusion([[10, 20, 30]])
    ids = [doc_id for doc_id, _ in out]
    assert ids == [10, 20, 30]


def test_two_rankings_merge_by_summed_reciprocal() -> None:
    # doc 1: rank 1 in r1, rank 2 in r2 -> 1/(60+1) + 1/(60+2) = ~0.0326
    # doc 2: rank 2 in r1, rank 1 in r2 -> 1/(60+2) + 1/(60+1) = ~0.0326 (tie)
    # doc 3: rank 3 in r1 only          -> 1/(60+3) = ~0.0159
    out = reciprocal_rank_fusion([[1, 2, 3], [2, 1]])
    ids = [doc_id for doc_id, _ in out]
    # 1 and 2 tie; 3 comes last
    assert set(ids[:2]) == {1, 2}
    assert ids[-1] == 3


def test_document_appearing_in_more_rankings_outscores_others() -> None:
    # doc A appears in all three; doc B in only one.
    out = reciprocal_rank_fusion([[1, 2], [1, 3], [1, 4]])
    ids = [doc_id for doc_id, _ in out]
    assert ids[0] == 1


def test_custom_k_changes_relative_weights() -> None:
    # With k=60 (default), early ranks dominate softly.
    # With k=1, the difference between rank-1 and rank-10 is much larger.
    out_default = reciprocal_rank_fusion([[1, 2]], k=60)
    out_aggressive = reciprocal_rank_fusion([[1, 2]], k=1)
    # The ratio score(1)/score(2) should be bigger with smaller k.
    d_score_1 = next(s for d, s in out_default if d == 1)
    d_score_2 = next(s for d, s in out_default if d == 2)
    a_score_1 = next(s for d, s in out_aggressive if d == 1)
    a_score_2 = next(s for d, s in out_aggressive if d == 2)
    assert (a_score_1 / a_score_2) > (d_score_1 / d_score_2)


def test_scores_are_positive_and_decreasing() -> None:
    out = reciprocal_rank_fusion([[1, 2, 3, 4, 5]])
    scores = [s for _, s in out]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)


def test_k_must_be_positive() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[1]], k=0)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([[1]], k=-5)
