from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_accounts import create_account
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_registry import enable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import auth_headers, register_and_login


def test_marketplace_publish_api_lifecycle_and_owner_scoping(client: TestClient) -> None:
    owner_token = register_and_login(client, "publish-api-owner@example.com")
    outsider_token = register_and_login(client, "publish-api-outsider@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "publish-api-owner@example.com")).one()
        marketplace = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == "HIPCOMIC")).one()
        enable_marketplace(session, marketplace_id=int(marketplace.id or 0))
        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="HipComic Publish",
                account_identifier="hipcomic-publish-api",
                status="ACTIVE",
            ),
        )
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Publish API Listing",
                listing_description="Publish API description",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="13.00",
                currency="USD",
                quantity=1,
            ),
        )
        ready = mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)
        listing_id = ready.listing.id
        marketplace_id = int(marketplace.id or 0)
        marketplace_account_id = account.id

    created = client.post(
        "/api/v1/marketplace-publish/jobs",
        headers=auth_headers(owner_token),
        json={
            "listing_id": listing_id,
            "targets": [{"marketplace_id": marketplace_id, "marketplace_account_id": marketplace_account_id}],
        },
    )
    assert created.status_code == 201, created.text
    job_id = created.json()["data"]["job"]["id"]

    validated = client.post(f"/api/v1/marketplace-publish/jobs/{job_id}/validate", headers=auth_headers(owner_token))
    planned = client.post(f"/api/v1/marketplace-publish/jobs/{job_id}/plan", headers=auth_headers(owner_token))
    ready = client.post(f"/api/v1/marketplace-publish/jobs/{job_id}/ready", headers=auth_headers(owner_token))
    completed = client.post(f"/api/v1/marketplace-publish/jobs/{job_id}/complete", headers=auth_headers(owner_token))
    detail = client.get(f"/api/v1/marketplace-publish/jobs/{job_id}", headers=auth_headers(owner_token))
    listing = client.get("/api/v1/marketplace-publish/jobs?limit=20&offset=0", headers=auth_headers(owner_token))
    denied = client.get(f"/api/v1/marketplace-publish/jobs/{job_id}", headers=auth_headers(outsider_token))

    assert validated.status_code == 200, validated.text
    assert planned.status_code == 200, planned.text
    assert ready.status_code == 200, ready.text
    assert completed.status_code == 200, completed.text
    assert detail.status_code == 200, detail.text
    assert listing.status_code == 200, listing.text
    assert denied.status_code == 404, denied.text
    assert completed.json()["data"]["job"]["status"] == "COMPLETED"
    assert detail.json()["data"]["targets"][0]["target_status"] == "SKIPPED"
    assert listing.json()["data"]["items"][0]["id"] == job_id
