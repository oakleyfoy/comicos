from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace_sync import MarketplaceOrder
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.whatnot import WhatnotConnectRequest
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_accounts import connect_account
from app.services.whatnot_connector import reset_whatnot_stub_state
from app.services.whatnot_listing_publish import publish_canonical_listing
from app.services.whatnot_order_import import import_orders
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_whatnot_order_import_and_duplicate_protection(client: TestClient) -> None:
    reset_whatnot_stub_state()
    register_and_login(client, "whatnot-orders@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "whatnot-orders@example.com")
        connect_account(
            session,
            owner_id=owner_id,
            payload=WhatnotConnectRequest(
                account_name="Orders Shop",
                account_identifier="whatnot-orders-1",
                api_token="whatnot_valid_orders",
            ),
        )
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Whatnot Order Listing",
                listing_description="Order import test",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="30.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=owner_id, listing_id=listing.listing.id)
        publish_canonical_listing(session, owner_id=owner_id, listing_id=listing.listing.id)

        first = import_orders(session, owner_id=owner_id)
        second = import_orders(session, owner_id=owner_id)
        orders = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.owner_id == owner_id)).all()

        assert first.imported_count >= 1
        assert second.skipped_duplicates >= 1
        assert len(orders) == first.imported_count
