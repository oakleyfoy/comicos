from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.whatnot import WhatnotConnectRequest
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_accounts import connect_account
from app.services.whatnot_connector import reset_whatnot_stub_state
from app.services.whatnot_inventory_sync import sync_availability
from app.services.whatnot_listing_publish import publish_canonical_listing
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_whatnot_inventory_sync_updates_stub_quantity(client: TestClient) -> None:
    reset_whatnot_stub_state()
    register_and_login(client, "whatnot-sync@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "whatnot-sync@example.com")
        connect_account(
            session,
            owner_id=owner_id,
            payload=WhatnotConnectRequest(
                account_name="Sync Shop",
                account_identifier="whatnot-sync-1",
                api_token="whatnot_valid_sync",
            ),
        )
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Whatnot Sync Listing",
                listing_description="Sync test",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="18.00",
                currency="USD",
                quantity=3,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=listing.listing.id)
        publish_canonical_listing(session, owner_id=owner_id, listing_id=listing.listing.id)
        result = sync_availability(session, owner_id=owner_id, listing_id=listing.listing.id)
        assert result.synced_items == 1
