"""P88-04 marketplace confidence tests."""

from datetime import datetime, timedelta, timezone

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.marketplace_confidence_service import score_listing_confidence


def _listing(**kwargs: object) -> P88MarketplaceListing:
    base = {
        "owner_user_id": 1,
        "marketplace": "EBAY",
        "item_id": "1",
        "title": "Absolute Batman #20",
        "listing_url": "https://ebay.com/itm/1",
        "price": 8.99,
        "shipping_cost": 0.0,
        "condition": "NM",
        "seller_name": "seller",
        "is_active": True,
        "health_status": "ACTIVE",
        "last_verified_at": datetime.now(timezone.utc),
    }
    base.update(kwargs)
    return P88MarketplaceListing(**base)  # type: ignore[arg-type]


def test_ebay_fresh_listing_high_confidence() -> None:
    assert score_listing_confidence(_listing()) == "HIGH"


def test_stale_retail_listing_lower_confidence() -> None:
    stale = _listing(
        marketplace="MYCOMICSHOP",
        last_verified_at=datetime.now(timezone.utc) - timedelta(days=60),
        title="",
        condition="",
        seller_name="",
    )
    assert score_listing_confidence(stale) in {"LOW", "MEDIUM"}
