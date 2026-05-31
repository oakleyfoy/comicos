from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_connector import reset_whatnot_stub_state
from test_inventory import auth_headers, register_and_login


def test_whatnot_api_owner_scoping_and_routes(client: TestClient) -> None:
    reset_whatnot_stub_state()
    owner_token = register_and_login(client, "whatnot-api-owner@example.com")
    outsider_token = register_and_login(client, "whatnot-api-outsider@example.com")

    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "whatnot-api-owner@example.com")).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Whatnot API Listing",
                listing_description="API route test",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="22.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)
        listing_id = listing.listing.id

    connect = client.post(
        "/api/v1/whatnot/connect",
        headers=auth_headers(owner_token),
        json={
            "account_name": "API Shop",
            "account_identifier": "whatnot-api-1",
            "api_token": "whatnot_valid_api_token",
        },
    )
    assert connect.status_code == 201, connect.text

    account = client.get("/api/v1/whatnot/account", headers=auth_headers(owner_token))
    validate = client.post("/api/v1/whatnot/validate", headers=auth_headers(owner_token))
    publish = client.post(f"/api/v1/whatnot/publish/{listing_id}", headers=auth_headers(owner_token))
    pause = client.post(f"/api/v1/whatnot/pause/{listing_id}", headers=auth_headers(owner_token))
    resume = client.post(f"/api/v1/whatnot/resume/{listing_id}", headers=auth_headers(owner_token))
    sync = client.post("/api/v1/whatnot/sync-inventory", headers=auth_headers(owner_token), params={"listing_id": listing_id})
    imports = client.post("/api/v1/whatnot/import-orders", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/whatnot/executions?limit=50&offset=0", headers=auth_headers(owner_token))
    denied = client.get("/api/v1/whatnot/account", headers=auth_headers(outsider_token))

    assert account.status_code == 200, account.text
    assert validate.status_code == 200, validate.text
    assert publish.status_code == 201, publish.text
    assert pause.status_code == 200, pause.text
    assert resume.status_code == 200, resume.text
    assert sync.status_code == 201, sync.text
    assert imports.status_code == 201, imports.text
    assert executions.status_code == 200, executions.text
    assert denied.status_code == 404, denied.text
    assert executions.json()["data"]["items"]
