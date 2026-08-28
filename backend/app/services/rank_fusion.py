"""Weighted Reciprocal Rank Fusion for hybrid keyword and semantic ranking."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
Identity = tuple[str, str]


@dataclass(frozen=True)
class FusedHit(Generic[T]):
    identity: Identity
    payload: T
    score: float
    keyword_rank: int | None
    semantic_rank: int | None
    keyword_contribution: float
    semantic_contribution: float
    exact_identifier_boost: float


def result_identity(result: object) -> Identity:
    return (result.result_type, result.id)


def fuse_weighted_rrf(
    keyword_items: Sequence[T],
    semantic_items: Sequence[T],
    *,
    rrf_k: int,
    keyword_weight: float = 1.0,
    semantic_weight: float = 1.0,
    identity: Callable[[T], Identity] = result_identity,
    exact_identifier_boost: Callable[[T], float] | None = None,
) -> list[FusedHit[T]]:
    keyword_ranks = _first_ranks(keyword_items, identity)
    semantic_ranks = _first_ranks(semantic_items, identity)
    boost_for = exact_identifier_boost or (lambda _item: 0.0)
    fused: list[FusedHit[T]] = []
    for key in dict.fromkeys([*keyword_ranks, *semantic_ranks]):
        keyword_rank, keyword_item = keyword_ranks.get(key, (None, None))
        semantic_rank, semantic_item = semantic_ranks.get(key, (None, None))
        payload = keyword_item if keyword_item is not None else semantic_item
        if payload is None:
            continue
        boost = 0.0
        if keyword_item is not None:
            boost = max(boost, boost_for(keyword_item))
        if semantic_item is not None:
            boost = max(boost, boost_for(semantic_item))
        keyword_contribution = _rrf_contribution(keyword_weight, keyword_rank, rrf_k)
        semantic_contribution = _rrf_contribution(semantic_weight, semantic_rank, rrf_k)
        fused.append(
            FusedHit(
                identity=key,
                payload=payload,
                score=keyword_contribution + semantic_contribution + boost,
                keyword_rank=keyword_rank,
                semantic_rank=semantic_rank,
                keyword_contribution=keyword_contribution,
                semantic_contribution=semantic_contribution,
                exact_identifier_boost=boost,
            )
        )
    fused.sort(key=lambda item: (-item.score, item.identity))
    return fused


def _rrf_contribution(weight: float, rank: int | None, rrf_k: int) -> float:
    if rank is None:
        return 0.0
    return weight / (rrf_k + rank)


def _first_ranks(
    items: Sequence[T], identity: Callable[[T], Identity]
) -> dict[Identity, tuple[int, T]]:
    ranks: dict[Identity, tuple[int, T]] = {}
    for index, item in enumerate(items, start=1):
        key = identity(item)
        if key not in ranks:
            ranks[key] = (index, item)
    return ranks
