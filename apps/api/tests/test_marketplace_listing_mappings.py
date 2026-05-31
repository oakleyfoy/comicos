from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingMappingCreate
from app.services.marketplace_accounts import create_account
from app.services.marketplace_listing_mappings import create_mapping, get_mapping, list_mappings_for_listing, update_mapping_status
from app.services.marketplace_listings import create_listing
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def test_marketplace_listing_mappings_create_and_update_status(client: TestClient) -> None:
    register_and_login(client, "listing-mapping-owner@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "listing-mapping-owner@example.com")).one()
        marketplace = session.exec(
            select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "SHOPIFY")
        ).one()
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Shopify Mapping Account",
                account_identifier="shopify-map-1",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Mapping Listing",
                listing_description="Testing mappings",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="25.00",
                currency="USD",
                quantity=1,
            ),
        )
        mapping = create_mapping(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            payload=MarketplaceListingMappingCreate(
                marketplace_id=int(marketplace.id or 0),
                marketplace_account_id=account.id,
                external_listing_id=None,
                external_url=None,
                sync_status="pending",
            ),
        )
        updated = update_mapping_status(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            mapping_id=mapping.id,
            sync_status="mapped",
            external_listing_id="shopify-123",
            external_url="https://example.com/listings/shopify-123",
        )
        listed = list_mappings_for_listing(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            limit=20,
            offset=0,
        )
        fetched = get_mapping(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            mapping_id=mapping.id,
        )

        assert mapping.sync_status == "PENDING"
        assert updated.sync_status == "MAPPED"
        assert updated.external_listing_id == "shopify-123"
        assert updated.last_synced_at is not None
        assert len(listed.items) == 1
        assert fetched.id == mapping.id
