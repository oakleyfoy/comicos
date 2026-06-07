from __future__ import annotations

from app.services.market_price_engine import compute_market_price


def test_market_price_trimmed_mean() -> None:
    price = compute_market_price(active_prices=[10.0, 12.0, 11.0, 13.0])
    assert 10.0 <= price <= 13.0


def test_market_price_empty() -> None:
    assert compute_market_price(active_prices=[]) == 0.0
