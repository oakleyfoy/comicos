"""P88-04 marketplace comparison tests."""

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.marketplace_comparison_service import compare_listings


def _listing(**kwargs: object) -> P88MarketplaceListing:
    base = {
        "owner_user_id": 1,
        "marketplace": "EBAY",
        "item_id": "1",
        "title": "Test",
        "listing_url": "https://ebay.com/itm/1",
        "price": 10.0,
        "shipping_cost": 0.0,
        "is_active": True,
        "health_status": "ACTIVE",
    }
    base.update(kwargs)
    return P88MarketplaceListing(**base)  # type: ignore[arg-type]


def test_lowest_total_cost_wins() -> None:
    rows = [
        _listing(marketplace="EBAY", item_id="1", price=8.99, shipping_cost=0.0),
        _listing(marketplace="MYCOMICSHOP", item_id="2", price=10.5, shipping_cost=0.0),
        _listing(marketplace="MIDTOWN", item_id="3", price=12.99, shipping_cost=0.0),
    ]
    result = compare_listings(rows)
    assert result.best_marketplace == "EBAY"
    assert result.best_total_cost == 8.99
    assert result.savings_vs_highest == 4.0


def test_shipping_included_in_ranking() -> None:
    rows = [
        _listing(marketplace="EBAY", item_id="1", price=5.0, shipping_cost=5.0),
        _listing(marketplace="MYCOMICSHOP", item_id="2", price=9.0, shipping_cost=0.0),
    ]
    result = compare_listings(rows)
    assert result.best_marketplace == "MYCOMICSHOP"
    assert result.best_total_cost == 9.0
