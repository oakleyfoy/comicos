from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace_listing import MarketplaceListing
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.shopify import ShopifyConnectRequest
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.shopify_accounts import connect_account
from app.services.shopify_connector import reset_shopify_stub_state
from app.services.shopify_product_publish import (
    archive_listing,
    publish_canonical_listing,
    restore_listing,
    update_canonical_listing,
)
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_shopify_publish_update_archive_and_restore(client: TestClient) -> None:
    reset_shopify_stub_state()
    register_and_login(client, "shopify-publish@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "shopify-publish@example.com")
        connect_account(
            session,
            owner_id=owner_id,
            payload=ShopifyConnectRequest(
                account_name="Publish Shop",
                shop_domain="publish.myshopify.com",
                admin_api_token="shopify_valid_publish",
            ),
        )
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Shopify Publish Listing",
                listing_description="Ready for Shopify",
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
        archived = archive_listing(session, owner_id=owner_id, listing_id=listing.listing.id)
        restored = restore_listing(session, owner_id=owner_id, listing_id=listing.listing.id)

        row = session.get(MarketplaceListing, listing.listing.id)
        assert published.external_listing_id
        assert updated.sync_status == "MAPPED"
        assert archived.sync_status == "ARCHIVED"
        assert restored.sync_status == "MAPPED"
        assert row is not None
        assert row.listing_title == title_before
