"""Tests for listing health service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.listing_health_service import (
    apply_health_to_listing,
    evaluate_listing_health,
    is_listing_displayable,
    listing_health_badges,
)


def _listing(**kwargs: object) -> P88MarketplaceListing:
    now = datetime.now(timezone.utc)
    base = dict(
        owner_user_id=1,
        marketplace="EBAY",
        item_id="1234567890",
        title="Comic",
        listing_url="https://www.ebay.com/itm/1234567890",
        price=5.0,
        shipping_cost=0.0,
        is_active=True,
        health_status="ACTIVE",
        last_verified_at=now,
    )
    base.update(kwargs)
    return P88MarketplaceListing(**base)  # type: ignore[arg-type]


def test_invalid_url_marks_invalid() -> None:
    row = _listing(listing_url="https://evil.example/itm/1")
    assert evaluate_listing_health(row) == "INVALID"


def test_ended_listing() -> None:
    past = datetime.now(timezone.utc) - timedelta(days=1)
    row = _listing(end_time=past, is_active=True)
    status = apply_health_to_listing(row)
    assert status == "ENDED"
    assert row.is_active is False


def test_stale_when_never_verified() -> None:
    row = _listing(last_verified_at=None)
    assert evaluate_listing_health(row) == "STALE"


def test_price_changed_badge() -> None:
    row = _listing(previous_price=10.0, price=8.0)
    badges = listing_health_badges(row)
    assert "Price Changed" in badges


def test_displayable_requires_active_valid() -> None:
    row = _listing()
    assert is_listing_displayable(row) is True
    row.health_status = "INVALID"
    assert is_listing_displayable(row) is False
