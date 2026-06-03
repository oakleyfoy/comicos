from __future__ import annotations

from dataclasses import dataclass, field

from app.services.recommendation_priority_spread import (
    MIN_CONF_GAP,
    MIN_RANK_GAP,
    SPREAD_CEILING,
    apply_confidence_spread_inplace,
    apply_priority_spread_inplace,
    composite_rank_score,
)


@dataclass
class _Item:
    title: str
    priority_score: float
    confidence_score: float
    estimated_value: float | None = None
    source_systems: set[str] = field(default_factory=set)
    raw_priority_score: float = 0.0
    normalized_priority_score: float = 0.0

    raw_confidence_score: float = 0.0
    normalized_confidence_score: float = 0.0

    @property
    def title_key(self) -> str:
        return self.title.lower()


def test_spread_breaks_flat_confidence_ceiling() -> None:
    items = [
        _Item(f"Title {i}", priority_score=90.0 - i, confidence_score=1.0, raw_confidence_score=0.86 - i * 0.02)
        for i in range(20)
    ]
    apply_confidence_spread_inplace(items)
    scores = [i.confidence_score for i in items]
    assert len({round(s, 4) for s in scores}) >= 15
    assert max(scores) <= 0.96
    assert min(scores) >= 0.52
    assert not all(abs(s - 1.0) < 1e-9 for s in scores)


def test_spread_breaks_flat_100_ceiling() -> None:
    items = [
        _Item(f"Title {i}", priority_score=100.0, confidence_score=0.86 - i * 0.015)
        for i in range(20)
    ]
    apply_priority_spread_inplace(items)
    scores = [i.priority_score for i in items]
    assert len({round(s, 1) for s in scores}) >= 15
    assert max(scores) - min(scores) > 10.0
    assert max(scores) <= SPREAD_CEILING
    assert all(i.normalized_priority_score == i.priority_score for i in items)
    assert all(i.raw_priority_score == 100.0 for i in items)


def test_composite_uses_confidence_when_priority_tied() -> None:
    high = composite_rank_score(
        raw_priority=100.0,
        confidence=0.9,
        estimated_value=None,
        source_count=2,
        title_key="alpha",
    )
    low = composite_rank_score(
        raw_priority=100.0,
        confidence=0.55,
        estimated_value=None,
        source_count=1,
        title_key="beta",
    )
    assert high > low


def test_adjacent_rank_gap_respected() -> None:
    items = [_Item(f"T{i}", 95.0 + i * 0.01, 0.7 + i * 0.01) for i in range(5)]
    apply_priority_spread_inplace(items)
    items.sort(key=lambda i: -i.priority_score)
    for idx in range(len(items) - 1):
        assert items[idx].priority_score - items[idx + 1].priority_score >= MIN_RANK_GAP - 1e-9
