"""Tests for verified P88 marketplace listing resolution (P90-07)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.verified_listing_service import (
    is_verified_marketplace_listing,
    pick_best_verified_listing,
    verified_listing_to_dict,
)


def _listing(**overrides) -> P88MarketplaceListing:
    now = datetime.now(timezone.utc)
    base = dict(
        owner_user_id=1,
        opportunity_id=10,
        marketplace="EBAY",
        item_id="1234567890",
        title="Absolute Batman #20",
        listing_url="https://www.ebay.com/itm/1234567890",
        price=4.49,
        shipping_cost=0.0,
        is_active=True,
        health_status="ACTIVE",
        last_verified_at=now,
        marketplace_name="eBay",
        listing_confidence="HIGH",
    )
    base.update(overrides)
    return P88MarketplaceListing(**base)


def test_verified_listing_requires_safe_url_and_active_health() -> None:
    row = _listing()
    assert is_verified_marketplace_listing(row) is True
    assert pick_best_verified_listing([row]) is row


def test_simulated_listing_is_not_verified() -> None:
    row = _listing(item_id="SIM-EBAY-1", listing_url="https://www.ebay.com/itm/sim-123")
    assert is_verified_marketplace_listing(row) is False


def test_ended_listing_is_not_verified() -> None:
    row = _listing(health_status="ENDED", is_active=False)
    assert is_verified_marketplace_listing(row) is False


def test_stale_listing_is_not_verified() -> None:
    row = _listing(health_status="STALE")
    assert is_verified_marketplace_listing(row) is False


def test_verified_listing_to_dict_includes_total_cost() -> None:
    row = _listing(shipping_cost=1.0)
    data = verified_listing_to_dict(row)
    assert data["total_cost"] == 5.49
    assert data["listing_url"].startswith("https://")
