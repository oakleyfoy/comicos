from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingPriceCreate
from app.services.marketplace_listing_prices import get_current_price, get_price_history, set_listing_price
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_marketplace_listing_prices_append_history_and_update_current_listing(client: TestClient) -> None:
    register_and_login(client, "listing-price-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "listing-price-owner@example.com")).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Price Listing",
                listing_description="Testing prices",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="14.00",
                currency="USD",
                quantity=1,
            ),
        )
        first = set_listing_price(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingPriceCreate(amount="15.00", currency="USD", price_type="ASKING"),
        )
        second = set_listing_price(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingPriceCreate(amount="16.50", currency="USD", price_type="ASKING"),
        )
        history = get_price_history(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            limit=20,
            offset=0,
        )
        current = get_current_price(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)

        assert str(first.amount) == "15.00"
        assert str(second.amount) == "16.50"
        assert len(history.items) == 2
        assert str(history.items[0].amount) == "16.50"
        assert current is not None
        assert str(current.amount) == "16.50"
