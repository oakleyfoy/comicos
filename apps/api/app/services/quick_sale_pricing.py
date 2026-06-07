"""P89-02 quick sale price estimation."""

from __future__ import annotations


def compute_quick_sale_price(
    *,
    active_prices: list[float],
    listing_count: int,
    sales_velocity: str,
) -> float:
    if not active_prices:
        return 0.0
    low = min(active_prices)
    avg = sum(active_prices) / len(active_prices)
    base = low * 0.98 + avg * 0.02
    if listing_count >= 6:
        base *= 0.97
    elif listing_count <= 1:
        base *= 1.02
    if sales_velocity in {"VERY_FAST", "FAST"}:
        base *= 0.98
    elif sales_velocity in {"VERY_SLOW", "SLOW"}:
        base *= 1.03
    return round(max(base, 0.01), 2)
