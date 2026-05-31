from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingMappingCreate
from app.schemas.marketplace_sync import MarketplaceInventoryReservationCreate, MarketplaceInventorySyncPlanGenerateRequest
from app.services.marketplace_accounts import create_account
from app.services.marketplace_inventory_reservations import create_reservation
from app.services.marketplace_inventory_sync_planner import generate_sync_plan
from app.services.marketplace_inventory_reservations import release_reservation
from app.services.marketplace_listing_mappings import create_mapping, update_mapping_status
from app.services.marketplace_listings import create_listing
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def test_marketplace_inventory_sync_planner_generates_actions_from_availability(client: TestClient) -> None:
    register_and_login(client, "sync-planner-owner@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "sync-planner-owner@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "SHOPIFY")).one()
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Sync Planner Account",
                account_identifier="sync-planner-account",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Planner Listing",
                listing_description="Planner listing description",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="22.00",
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
                external_listing_id="shopify-item-1",
                external_url="https://example.com/listings/shopify-item-1",
                sync_status="mapped",
            ),
        )

        update_plan = generate_sync_plan(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceInventorySyncPlanGenerateRequest(listing_ids=[listing.listing.id]),
        )
        assert update_plan.items[0].action_type == "UPDATE_QUANTITY"

        reservation = create_reservation(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceInventoryReservationCreate(
                listing_id=listing.listing.id,
                inventory_copy_id=None,
                reservation_type="cart_hold",
                quantity_reserved=1,
                source="planner_hold",
                expires_at=None,
            ),
        )
        pause_plan = generate_sync_plan(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceInventorySyncPlanGenerateRequest(listing_ids=[listing.listing.id]),
        )
        assert pause_plan.items[0].action_type == "PAUSE_LISTING"

        update_mapping_status(
            session,
            owner_id=int(owner.id or 0),
            listing_id=listing.listing.id,
            mapping_id=mapping.id,
            sync_status="paused",
            external_listing_id="shopify-item-1",
            external_url="https://example.com/listings/shopify-item-1",
        )
        release_reservation(session, owner_id=int(owner.id or 0), reservation_id=reservation.id)
        resume_plan = generate_sync_plan(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceInventorySyncPlanGenerateRequest(listing_ids=[listing.listing.id]),
        )
        assert resume_plan.items[0].action_type == "RESUME_LISTING"
