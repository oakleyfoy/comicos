from __future__ import annotations

from app.services.quick_sale_pricing import compute_quick_sale_price


def test_quick_sale_favors_lowest_active_price() -> None:
    price = compute_quick_sale_price(
        active_prices=[45.0, 38.0, 40.0],
        listing_count=3,
        sales_velocity="NORMAL",
    )
    assert price <= 39.0
    assert price >= 36.0


def test_quick_sale_velocity_adjustment() -> None:
    fast = compute_quick_sale_price(active_prices=[50.0], listing_count=2, sales_velocity="VERY_FAST")
    slow = compute_quick_sale_price(active_prices=[50.0], listing_count=2, sales_velocity="VERY_SLOW")
    assert fast < slow
