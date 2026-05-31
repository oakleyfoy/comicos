from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate, MarketplaceListingMappingCreate
from app.schemas.marketplace_publish import MarketplacePublishRequest
from app.services.marketplace_accounts import create_account
from app.services.marketplace_listing_mappings import create_mapping
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_publish_planner import build_publish_plan
from app.services.marketplace_registry import enable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def test_publish_planner_builds_target_payload_from_canonical_listing(client: TestClient) -> None:
    register_and_login(client, "publish-planner-owner@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "publish-planner-owner@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "WHATNOT")).one()
        enable_marketplace(session, marketplace_id=int(marketplace.id or 0))
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Whatnot Publish",
                account_identifier="whatnot-publish-planner",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Planner Listing",
                listing_description="Planner description",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                grade_label="9.8",
                asking_price="31.25",
                currency="USD",
                quantity=2,
            ),
        )
        ready = mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)
        mapping = create_mapping(
            session,
            owner_id=int(owner.id or 0),
            listing_id=ready.listing.id,
            payload=MarketplaceListingMappingCreate(
                marketplace_id=int(marketplace.id or 0),
                marketplace_account_id=account.id,
                external_listing_id="draft-123",
                external_url="https://example.com/draft-123",
                sync_status="PENDING",
            ),
        )

        plan = build_publish_plan(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplacePublishRequest(
                listing_id=ready.listing.id,
                targets=[{"marketplace_id": int(marketplace.id or 0), "marketplace_account_id": account.id}],
            ),
        )

        assert len(plan) == 1
        assert plan[0]["listing_mapping_id"] == mapping.id
        payload = plan[0]["planned_payload_json"]
        assert payload["canonical_listing"]["listing_title"] == "Planner Listing"
        assert payload["canonical_listing"]["asking_price"] == "31.25"
        assert payload["marketplace"]["marketplace_code"] == "WHATNOT"
        assert payload["mapping"]["external_listing_id"] == "draft-123"
