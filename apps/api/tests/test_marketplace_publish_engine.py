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
from app.services.marketplace_publish_engine import (
    complete_publish_job,
    create_publish_job,
    get_publish_job,
    plan_publish_job,
    ready_publish_job,
    validate_job_request,
)
from app.services.marketplace_registry import enable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def test_publish_engine_lifecycle_and_append_only_events(client: TestClient) -> None:
    register_and_login(client, "publish-engine-owner@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "publish-engine-owner@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "EBAY")).one()
        enable_marketplace(session, marketplace_id=int(marketplace.id or 0))
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="eBay Publish",
                account_identifier="ebay-publish-engine",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Engine Listing",
                listing_description="Engine description",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="19.00",
                currency="USD",
                quantity=1,
            ),
        )
        ready_listing = mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)
        request = MarketplacePublishRequest(
            listing_id=ready_listing.listing.id,
            targets=[{"marketplace_id": int(marketplace.id or 0), "marketplace_account_id": account.id}],
        )

        created = create_publish_job(
            session,
            owner_id=int(owner.id or 0),
            requested_by=int(owner.id or 0),
            payload=request,
        )
        validated = validate_job_request(session, owner_id=int(owner.id or 0), job_id=created.job.id, payload=request)
        planned = plan_publish_job(session, owner_id=int(owner.id or 0), job_id=created.job.id, payload=request)
        ready = ready_publish_job(session, owner_id=int(owner.id or 0), job_id=created.job.id)
        completed = complete_publish_job(session, owner_id=int(owner.id or 0), job_id=created.job.id)
        detail = get_publish_job(session, owner_id=int(owner.id or 0), job_id=created.job.id)

        assert created.job.status == "PENDING"
        assert validated.job.status == "VALIDATING"
        assert planned.job.status == "PLANNED"
        assert planned.targets[0].target_status == "PLANNED"
        assert ready.job.status == "READY"
        assert completed.job.status == "COMPLETED"
        assert detail.targets[0].target_status == "SKIPPED"
        assert [event.event_type for event in detail.events] == [
            "publish_job_created",
            "publish_plan_created",
            "publish_job_ready",
            "publish_job_completed",
        ]


def test_publish_engine_records_validation_issues(client: TestClient) -> None:
    register_and_login(client, "publish-engine-invalid@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "publish-engine-invalid@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "SHOPIFY")).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Invalid Publish Listing",
                listing_description="Not ready",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="7.50",
                currency="USD",
                quantity=1,
            ),
        )
        request = MarketplacePublishRequest(
            listing_id=listing.listing.id,
            targets=[{"marketplace_id": int(marketplace.id or 0), "marketplace_account_id": None}],
        )
        created = create_publish_job(
            session,
            owner_id=int(owner.id or 0),
            requested_by=int(owner.id or 0),
            payload=request,
        )
        validated = validate_job_request(session, owner_id=int(owner.id or 0), job_id=created.job.id, payload=request)

        assert validated.job.status == "FAILED"
        assert [issue.issue_code for issue in validated.validation_issues] == [
            "listing_not_ready",
            "target_0_marketplace_disabled",
        ]
        assert validated.events[-2].event_type == "publish_validation_failed"
        assert validated.events[-1].event_type == "publish_job_failed"
