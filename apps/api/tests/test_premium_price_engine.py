from __future__ import annotations

from app.services.premium_price_engine import compute_premium_price


def test_premium_at_or_above_market() -> None:
    premium = compute_premium_price(active_prices=[30.0, 45.0, 38.0], listing_count=3, market_price=36.0)
    assert premium >= 36.0


def test_premium_scarcity_boost() -> None:
    premium = compute_premium_price(active_prices=[80.0, 55.0], listing_count=1, market_price=60.0)
    assert premium >= 60.0 * 1.05
