from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace_listing import MarketplaceListing
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.whatnot import WhatnotConnectRequest
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_accounts import connect_account
from app.services.whatnot_connector import reset_whatnot_stub_state
from app.services.whatnot_listing_publish import pause_listing, publish_canonical_listing, resume_listing, update_canonical_listing
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_whatnot_publish_update_pause_and_resume(client: TestClient) -> None:
    reset_whatnot_stub_state()
    register_and_login(client, "whatnot-publish@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "whatnot-publish@example.com")
        connect_account(
            session,
            owner_id=owner_id,
            payload=WhatnotConnectRequest(
                account_name="Publish Shop",
                account_identifier="whatnot-publish-1",
                api_token="whatnot_valid_publish",
            ),
        )
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Whatnot Publish Listing",
                listing_description="Ready for Whatnot",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="25.00",
                currency="USD",
                quantity=2,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=listing.listing.id)
        title_before = listing.listing.listing_title

        published = publish_canonical_listing(session, owner_id=owner_id, listing_id=listing.listing.id)
        updated = update_canonical_listing(session, owner_id=owner_id, listing_id=listing.listing.id)
        paused = pause_listing(session, owner_id=owner_id, listing_id=listing.listing.id)
        resumed = resume_listing(session, owner_id=owner_id, listing_id=listing.listing.id)

        row = session.get(MarketplaceListing, listing.listing.id)
        assert published.external_listing_id
        assert updated.sync_status == "MAPPED"
        assert paused.sync_status == "PAUSED"
        assert resumed.sync_status == "MAPPED"
        assert row is not None
        assert row.listing_title == title_before
