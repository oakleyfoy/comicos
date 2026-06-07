"""P88-04 best buy service tests."""

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.adapters.adapter_registry import get_marketplace_adapter
from app.services.marketplace.best_buy_service import recommend_best_buy


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
        "last_verified_at": None,
    }
    base.update(kwargs)
    return P88MarketplaceListing(**base)  # type: ignore[arg-type]


def test_best_buy_recommends_lowest_total_cost() -> None:
    rec = recommend_best_buy(
        [
            _listing(marketplace="EBAY", item_id="1", price=8.99),
            _listing(marketplace="MIDTOWN", item_id="2", price=12.99),
        ]
    )
    assert rec.marketplace == "EBAY"
    assert rec.total_cost == 8.99
    assert "Lowest total cost" in rec.reason


def test_unsupported_adapter_returns_not_supported() -> None:
    adapter = get_marketplace_adapter("MYCOMICSHOP")
    result = adapter.search(query="Batman", limit=5)
    assert result.status == "NOT_SUPPORTED"
    assert not result.listings
