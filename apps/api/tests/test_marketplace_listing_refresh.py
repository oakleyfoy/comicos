"""Tests for marketplace listing refresh."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models.p88_marketplace_listing import P88MarketplaceListing
from app.services.marketplace.ebay_search_service import NormalizedMarketplaceListing
from app.services.marketplace.marketplace_listing_refresh_service import refresh_marketplace_listing


def test_refresh_marks_ended_when_item_missing() -> None:
    row = P88MarketplaceListing(
        owner_user_id=1,
        marketplace="EBAY",
        item_id="111",
        title="Old",
        listing_url="https://www.ebay.com/itm/111",
        price=1.0,
        is_active=True,
        health_status="ACTIVE",
    )
    session = MagicMock()

    with patch("app.services.marketplace.marketplace_listing_refresh_service.fetch_item_by_id", return_value=None):
        refresh_marketplace_listing(session, listing=row, settings=MagicMock())
    assert row.health_status == "ENDED"
    assert row.is_active is False


def test_refresh_updates_price() -> None:
    row = P88MarketplaceListing(
        owner_user_id=1,
        marketplace="EBAY",
        item_id="222",
        title="Comic",
        listing_url="https://www.ebay.com/itm/222",
        price=5.0,
        is_active=True,
        health_status="ACTIVE",
    )
    session = MagicMock()
    fetched = NormalizedMarketplaceListing(
        marketplace="EBAY",
        item_id="222",
        title="Comic Updated",
        url="https://www.ebay.com/itm/222",
        price=4.0,
        shipping=1.0,
        condition="NM",
        seller="seller1",
        listing_type="FIXED_PRICE",
        end_time=None,
        image_url="",
    )
    with patch(
        "app.services.marketplace.marketplace_listing_refresh_service.fetch_item_by_id",
        return_value=fetched,
    ):
        refresh_marketplace_listing(session, listing=row, settings=MagicMock())
    assert row.price == 4.0
    assert row.previous_price == 5.0
    assert row.health_status == "ACTIVE"
