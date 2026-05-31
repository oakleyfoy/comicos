from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.schemas.marketplace_publish import MarketplacePublishRequest
from app.services.marketplace_accounts import create_account
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_publish_validation import validate_publish_request
from app.services.marketplace_registry import enable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def test_publish_validation_returns_deterministic_issues(client: TestClient) -> None:
    register_and_login(client, "publish-validation-owner@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "publish-validation-owner@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "EBAY")).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Validation Listing",
                listing_description="Validation test",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="15.00",
                currency="USD",
                quantity=1,
            ),
        )
        issues = validate_publish_request(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplacePublishRequest(
                listing_id=listing.listing.id,
                targets=[{"marketplace_id": int(marketplace.id or 0), "marketplace_account_id": None}],
            ),
        )

        assert [issue.issue_code for issue in issues] == ["listing_not_ready", "target_0_marketplace_disabled"]


def test_publish_validation_accepts_ready_listing_on_enabled_marketplace(client: TestClient) -> None:
    register_and_login(client, "publish-validation-pass@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "publish-validation-pass@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "SHOPIFY")).one()
        enable_marketplace(session, marketplace_id=int(marketplace.id or 0))
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Shopify Publish",
                account_identifier="shopify-publish-validation",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Ready Listing",
                listing_description="Ready to publish",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="22.00",
                currency="USD",
                quantity=1,
            ),
        )
        ready = mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)

        issues = validate_publish_request(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplacePublishRequest(
                listing_id=ready.listing.id,
                targets=[{"marketplace_id": int(marketplace.id or 0), "marketplace_account_id": account.id}],
            ),
        )

        assert issues == []
