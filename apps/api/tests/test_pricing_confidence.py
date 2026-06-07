from __future__ import annotations

from datetime import datetime, timezone

from app.services.pricing_confidence_service import score_pricing_confidence


def test_confidence_high() -> None:
    level = score_pricing_confidence(
        listing_count=10,
        marketplace_sources=2,
        price_spread_ratio=0.12,
        latest_observation_at=datetime.now(timezone.utc),
    )
    assert level == "HIGH"


def test_confidence_low_sparse() -> None:
    level = score_pricing_confidence(
        listing_count=0,
        marketplace_sources=0,
        price_spread_ratio=0.9,
        latest_observation_at=None,
    )
    assert level == "LOW"
