"""P90 FMV confidence tests."""

from __future__ import annotations

from app.services.fmv_confidence_service import score_fmv_confidence


def test_velocity_adjusts_confidence() -> None:
    fast = score_fmv_confidence(
        listing_count=6,
        marketplace_count=2,
        price_spread_ratio=0.15,
        latest_observation_at=None,
        sales_velocity="VERY_FAST",
    )
    slow = score_fmv_confidence(
        listing_count=6,
        marketplace_count=2,
        price_spread_ratio=0.15,
        latest_observation_at=None,
        sales_velocity="VERY_SLOW",
    )
    rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    assert rank[fast] >= rank[slow]
