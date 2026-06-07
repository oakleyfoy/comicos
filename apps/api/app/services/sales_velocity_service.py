"""P89-02 sales velocity classification."""

from __future__ import annotations


def classify_sales_velocity(
    *,
    listing_count: int,
    sold_count: int,
    price_spread_ratio: float,
) -> str:
    activity = listing_count + sold_count * 2
    if activity >= 14 and price_spread_ratio <= 0.22:
        return "VERY_FAST"
    if activity >= 8 and price_spread_ratio <= 0.35:
        return "FAST"
    if activity >= 3:
        return "NORMAL"
    if activity >= 1:
        return "SLOW"
    return "VERY_SLOW"


def velocity_display_label(velocity: str) -> str:
    if velocity in {"VERY_FAST", "FAST"}:
        return "Likely to sell quickly"
    if velocity == "NORMAL":
        return "Typical market pace"
    return "May require patience"
