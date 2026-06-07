"""P90-02 FMV confidence scoring."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.pricing_confidence_service import score_pricing_confidence


_VELOCITY_ADJ = {
    "VERY_FAST": 0.08,
    "FAST": 0.05,
    "NORMAL": 0.0,
    "SLOW": -0.06,
    "VERY_SLOW": -0.12,
}


def _rank(confidence: str) -> int:
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(confidence, 1)


def _from_rank(rank: int) -> str:
    if rank >= 3:
        return "HIGH"
    if rank >= 2:
        return "MEDIUM"
    return "LOW"


def score_fmv_confidence(
    *,
    listing_count: int,
    marketplace_count: int,
    price_spread_ratio: float,
    latest_observation_at: datetime | None,
    sales_velocity: str,
    historical_consistency: float | None = None,
) -> str:
    base = score_pricing_confidence(
        listing_count=listing_count,
        marketplace_sources=marketplace_count,
        price_spread_ratio=price_spread_ratio,
        latest_observation_at=latest_observation_at,
    )
    rank = _rank(base) + int(round(_VELOCITY_ADJ.get(sales_velocity, 0.0) * 10))
    if historical_consistency is not None:
        if historical_consistency >= 0.85:
            rank += 1
        elif historical_consistency < 0.5:
            rank -= 1
    return _from_rank(max(1, min(3, rank)))
