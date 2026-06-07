"""P89-02 pricing confidence from stored marketplace data."""

from __future__ import annotations

from datetime import datetime, timezone


def score_pricing_confidence(
    *,
    listing_count: int,
    marketplace_sources: int,
    price_spread_ratio: float,
    latest_observation_at: datetime | None,
) -> str:
    score = 0.0
    if listing_count >= 8:
        score += 0.35
    elif listing_count >= 4:
        score += 0.25
    elif listing_count >= 1:
        score += 0.12
    if marketplace_sources >= 2:
        score += 0.2
    elif marketplace_sources >= 1:
        score += 0.1
    if price_spread_ratio <= 0.2:
        score += 0.2
    elif price_spread_ratio <= 0.4:
        score += 0.1
    if latest_observation_at is not None:
        observed = latest_observation_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - observed).days
        if age_days <= 3:
            score += 0.25
        elif age_days <= 14:
            score += 0.15
        elif age_days <= 45:
            score += 0.05
    if score >= 0.72:
        return "HIGH"
    if score >= 0.42:
        return "MEDIUM"
    return "LOW"
