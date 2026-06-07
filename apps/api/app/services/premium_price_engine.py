"""P89-02 premium listing price estimation."""

from __future__ import annotations


def compute_premium_price(
    *,
    active_prices: list[float],
    listing_count: int,
    market_price: float,
) -> float:
    if not active_prices:
        return round(max(market_price, 0.0), 2)
    high = max(active_prices)
    spread = high - min(active_prices)
    premium = high * 0.96
    if listing_count <= 2 and spread > 0:
        premium = max(premium, market_price * 1.12)
    elif spread >= market_price * 0.25:
        premium = max(premium, market_price * 1.08)
    premium = max(premium, market_price * 1.05)
    return round(premium, 2)
