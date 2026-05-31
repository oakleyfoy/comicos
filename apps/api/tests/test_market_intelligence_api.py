from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing, mark_ready_to_publish
from test_inventory import auth_headers, register_and_login


def test_market_intelligence_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "market-intelligence-owner@example.com"
    outsider_email = "market-intelligence-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        listing = create_listing(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceListingCreate(
                listing_title="Market Intelligence API Listing",
                listing_description="API route coverage",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="24.00",
                currency="USD",
                quantity=1,
            ),
        )
        mark_ready_to_publish(session, owner_id=int(owner.id or 0), listing_id=listing.listing.id)

    signals_run = client.post("/api/v1/market-intelligence/run/signals", headers=auth_headers(owner_token))
    snapshot_run = client.post("/api/v1/market-intelligence/run/snapshot", headers=auth_headers(owner_token))
    trends_run = client.post("/api/v1/market-intelligence/run/trends", headers=auth_headers(owner_token))
    observations_run = client.post("/api/v1/market-intelligence/run/observations", headers=auth_headers(owner_token))

    assert signals_run.status_code == 201, signals_run.text
    assert snapshot_run.status_code == 201, snapshot_run.text
    assert trends_run.status_code == 201, trends_run.text
    assert observations_run.status_code == 201, observations_run.text

    dashboard = client.get("/api/v1/market-intelligence/dashboard", headers=auth_headers(owner_token))
    signals = client.get("/api/v1/market-intelligence/signals?limit=100&offset=0", headers=auth_headers(owner_token))
    snapshots = client.get("/api/v1/market-intelligence/snapshots?limit=100&offset=0", headers=auth_headers(owner_token))
    trends = client.get("/api/v1/market-intelligence/trends?limit=100&offset=0", headers=auth_headers(owner_token))
    observations = client.get(
        "/api/v1/market-intelligence/observations?limit=100&offset=0",
        headers=auth_headers(owner_token),
    )
    executions = client.get("/api/v1/market-intelligence/executions?limit=100&offset=0", headers=auth_headers(owner_token))
    outsider_signals = client.get(
        "/api/v1/market-intelligence/signals?limit=100&offset=0",
        headers=auth_headers(outsider_token),
    )

    assert dashboard.status_code == 200, dashboard.text
    assert signals.status_code == 200, signals.text
    assert snapshots.status_code == 200, snapshots.text
    assert trends.status_code == 200, trends.text
    assert observations.status_code == 200, observations.text
    assert executions.status_code == 200, executions.text

    assert dashboard.json()["data"]["market_score"] >= 0
    assert signals.json()["data"]["items"]
    assert snapshots.json()["data"]["items"]
    assert observations.json()["data"]["items"]
    assert executions.json()["data"]["items"]
    assert outsider_signals.json()["data"]["items"] == []
