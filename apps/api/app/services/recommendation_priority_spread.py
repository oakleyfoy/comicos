"""Spread persisted recommendation priorities so ranking is not flattened at 100.0."""

from __future__ import annotations

from typing import Protocol, Sequence

SPREAD_FLOOR = 58.0
SPREAD_CEILING = 98.0
MIN_RANK_GAP = 0.55

CONF_SPREAD_FLOOR = 0.52
CONF_SPREAD_CEILING = 0.96
MIN_CONF_GAP = 0.012


def compress_additive_bonus(bonus: float, *, soft_cap: float = 22.0, tail_factor: float = 0.35) -> float:
    """Diminish returns on large stacked bonuses before hard ceiling."""
    extra = max(0.0, float(bonus) - soft_cap)
    return float(bonus) - extra + extra * tail_factor


def composite_rank_score(
    *,
    raw_priority: float,
    confidence: float,
    estimated_value: float | None,
    source_count: int,
    title_key: str,
) -> float:
    est = min(float(estimated_value or 0.0), 2500.0)
    jitter = (sum(ord(c) for c in (title_key or "")[:28]) % 997) * 0.0015
    return (
        float(raw_priority) * 0.42
        + float(confidence) * 54.0
        + est * 0.011
        + max(1, int(source_count)) * 1.35
        + jitter
    )


def _assign_spread_from_composites(composites: Sequence[float]) -> list[float]:
    if not composites:
        return []
    n = len(composites)
    lo = min(composites)
    hi = max(composites)
    if hi - lo < 1e-9:
        return [
            round(max(SPREAD_FLOOR, SPREAD_CEILING - idx * MIN_RANK_GAP), 1)
            for idx in range(n)
        ]
    span = SPREAD_CEILING - SPREAD_FLOOR
    mapped = [SPREAD_FLOOR + (c - lo) / (hi - lo) * span for c in composites]
    out: list[float] = [mapped[0]]
    for idx in range(1, n):
        capped = min(mapped[idx], out[-1] - MIN_RANK_GAP)
        out.append(capped)
    return [round(max(SPREAD_FLOOR, min(SPREAD_CEILING, s)), 1) for s in out]


class _SpreadTarget(Protocol):
    priority_score: float
    confidence_score: float
    estimated_value: float | None
    source_systems: set[str]

    @property
    def title_key(self) -> str: ...


def apply_priority_spread_inplace(
    items: Sequence[_SpreadTarget],
    *,
    raw_attr: str = "raw_priority_score",
    normalized_attr: str = "normalized_priority_score",
) -> None:
    """Re-rank items by composite score and assign spread priority_score values."""
    if not items:
        return
    raws: list[float] = []
    composites: list[float] = []
    for item in items:
        stored_raw = float(getattr(item, raw_attr, 0.0) or 0.0)
        raw = max(stored_raw, float(item.priority_score))
        setattr(item, raw_attr, raw)
        raws.append(raw)
        composites.append(
            composite_rank_score(
                raw_priority=raw,
                confidence=float(item.confidence_score),
                estimated_value=getattr(item, "estimated_value", None),
                source_count=len(getattr(item, "source_systems", None) or []),
                title_key=item.title_key,
            )
        )
    order = sorted(range(len(items)), key=lambda i: (-composites[i], -raws[i], items[i].title_key))
    spread = _assign_spread_from_composites([composites[i] for i in order])
    for rank_idx, orig_idx in enumerate(order):
        item = items[orig_idx]
        setattr(item, normalized_attr, spread[rank_idx])
        item.priority_score = spread[rank_idx]


def _assign_confidence_spread(composites: Sequence[float]) -> list[float]:
    if not composites:
        return []
    n = len(composites)
    lo = min(composites)
    hi = max(composites)
    if hi - lo < 1e-9:
        return [
            round(max(CONF_SPREAD_FLOOR, CONF_SPREAD_CEILING - idx * MIN_CONF_GAP), 4)
            for idx in range(n)
        ]
    span = CONF_SPREAD_CEILING - CONF_SPREAD_FLOOR
    mapped = [CONF_SPREAD_FLOOR + (c - lo) / (hi - lo) * span for c in composites]
    out: list[float] = [mapped[0]]
    for idx in range(1, n):
        capped = min(mapped[idx], out[-1] - MIN_CONF_GAP)
        out.append(capped)
    return [round(max(CONF_SPREAD_FLOOR, min(CONF_SPREAD_CEILING, s)), 4) for s in out]


def apply_confidence_spread_inplace(
    items: Sequence[_SpreadTarget],
    *,
    raw_attr: str = "raw_confidence_score",
    normalized_attr: str = "normalized_confidence_score",
) -> None:
    """Spread confidence so multi-source merge boosts do not flatten everything to 1.0."""
    if not items:
        return
    raws: list[float] = []
    composites: list[float] = []
    for item in items:
        stored_raw = float(getattr(item, raw_attr, 0.0) or 0.0)
        working = float(item.confidence_score)
        raw = stored_raw if stored_raw > 0.0 else working
        if working >= 0.999 and raw < 0.999:
            raw = min(raw, working)
        setattr(item, raw_attr, round(raw, 4))
        raws.append(raw)
        est = min(float(getattr(item, "estimated_value", None) or 0.0), 2500.0)
        composites.append(
            raw * 0.88
            + float(item.priority_score) * 0.0025
            + est * 0.00004
            + max(1, len(getattr(item, "source_systems", None) or [])) * 0.004
            + (sum(ord(c) for c in item.title_key[:20]) % 503) * 0.00001
        )
    order = sorted(range(len(items)), key=lambda i: (-composites[i], -raws[i], items[i].title_key))
    spread = _assign_confidence_spread([composites[i] for i in order])
    for rank_idx, orig_idx in enumerate(order):
        item = items[orig_idx]
        setattr(item, normalized_attr, spread[rank_idx])
        item.confidence_score = spread[rank_idx]
