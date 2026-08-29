from types import SimpleNamespace

import pytest

from app.services.rank_fusion import fuse_weighted_rrf


def _hit(result_type: str, item_id: str, *, title: str | None = None):
    return SimpleNamespace(
        result_type=result_type,
        id=item_id,
        title=title or item_id,
    )


def test_keyword_only_scores_use_weighted_rrf_ranks():
    fused = fuse_weighted_rrf(
        [_hit("ACT", "act-1"), _hit("SECTION", "sec-1")],
        [],
        rrf_k=60,
        keyword_weight=1.0,
        semantic_weight=1.0,
    )

    assert [item.identity for item in fused] == [("ACT", "act-1"), ("SECTION", "sec-1")]
    assert fused[0].score == pytest.approx(1.0 / (60 + 1))
    assert fused[1].score == pytest.approx(1.0 / (60 + 2))
    assert fused[0].keyword_rank == 1
    assert fused[0].semantic_rank is None
    assert fused[0].keyword_contribution == pytest.approx(1.0 / 61)
    assert fused[0].semantic_contribution == 0.0
    assert fused[0].payload.id == "act-1"


def test_semantic_only_scores_use_weighted_rrf_ranks():
    fused = fuse_weighted_rrf(
        [],
        [_hit("SECTION", "sec-near"), _hit("SECTION", "sec-far")],
        rrf_k=60,
        keyword_weight=1.0,
        semantic_weight=1.0,
    )

    assert [item.identity for item in fused] == [
        ("SECTION", "sec-near"),
        ("SECTION", "sec-far"),
    ]
    assert fused[0].score == pytest.approx(1.0 / 61)
    assert fused[0].keyword_rank is None
    assert fused[0].semantic_rank == 1


def test_overlap_adds_keyword_and_semantic_contributions():
    fused = fuse_weighted_rrf(
        [_hit("SECTION", "shared"), _hit("ACT", "act-only")],
        [_hit("SECTION", "sem-only"), _hit("SECTION", "shared")],
        rrf_k=60,
        keyword_weight=1.0,
        semantic_weight=1.0,
    )

    by_id = {item.identity: item for item in fused}
    shared = by_id[("SECTION", "shared")]
    assert shared.keyword_rank == 1
    assert shared.semantic_rank == 2
    assert shared.score == pytest.approx(1.0 / 61 + 1.0 / 62)
    assert shared.payload.id == "shared"
    assert by_id[("ACT", "act-only")].semantic_rank is None
    assert by_id[("SECTION", "sem-only")].keyword_rank is None
    assert fused[0].identity == ("SECTION", "shared")


def test_duplicate_identities_keep_the_first_rank():
    fused = fuse_weighted_rrf(
        [_hit("SECTION", "dup"), _hit("SECTION", "dup"), _hit("ACT", "other")],
        [_hit("SECTION", "dup")],
        rrf_k=10,
        keyword_weight=1.0,
        semantic_weight=1.0,
    )

    dup = next(item for item in fused if item.identity == ("SECTION", "dup"))
    assert dup.keyword_rank == 1
    assert dup.semantic_rank == 1
    assert fused[0].identity == ("SECTION", "dup")
    assert len(fused) == 2


def test_equal_rrf_scores_break_ties_by_identity():
    fused = fuse_weighted_rrf(
        [_hit("SECTION", "sec-b"), _hit("ACT", "act-a")],
        [],
        rrf_k=60,
        keyword_weight=0.0,
        semantic_weight=1.0,
    )

    assert [item.identity for item in fused] == [("ACT", "act-a"), ("SECTION", "sec-b")]
    assert fused[0].score == fused[1].score == 0.0


def test_exact_identifier_boost_dominates_semantic_rank_one():
    keyword = [_hit("ACT", "exact-act")]
    semantic = [_hit("SECTION", "near-section")]

    fused = fuse_weighted_rrf(
        keyword,
        semantic,
        rrf_k=60,
        keyword_weight=1.0,
        semantic_weight=1.0,
        exact_identifier_boost=lambda item: 200.0 if item.id == "exact-act" else 0.0,
    )

    assert fused[0].identity == ("ACT", "exact-act")
    assert fused[0].score == pytest.approx(1.0 / 61 + 200.0)
    assert fused[1].identity == ("SECTION", "near-section")
    assert fused[1].score == pytest.approx(1.0 / 61)
    assert fused[0].score > fused[1].score


def test_weighted_lists_scale_each_rank_contribution():
    fused = fuse_weighted_rrf(
        [_hit("SECTION", "shared")],
        [_hit("SECTION", "shared")],
        rrf_k=10,
        keyword_weight=2.0,
        semantic_weight=0.5,
    )

    assert fused[0].score == pytest.approx(2.0 / 11 + 0.5 / 11)
    assert fused[0].keyword_contribution == pytest.approx(2.0 / 11)
    assert fused[0].semantic_contribution == pytest.approx(0.5 / 11)
