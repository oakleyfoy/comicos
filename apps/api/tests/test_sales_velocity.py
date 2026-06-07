from __future__ import annotations

from app.services.sales_velocity_service import classify_sales_velocity, velocity_display_label


def test_velocity_very_fast() -> None:
    assert classify_sales_velocity(listing_count=10, sold_count=3, price_spread_ratio=0.15) == "VERY_FAST"


def test_velocity_very_slow() -> None:
    assert classify_sales_velocity(listing_count=0, sold_count=0, price_spread_ratio=0.5) == "VERY_SLOW"


def test_velocity_label() -> None:
    assert "quickly" in velocity_display_label("FAST").lower()
