from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketSignal, MarketTrend, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing
from test_inventory import auth_headers, register_and_login


def _seed_forecast_inputs(session: Session, *, owner_user_id: int) -> None:
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Forecast API Listing",
            listing_description="Forecast API seed",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="30.00",
            currency="USD",
            quantity=1,
        ),
    )
    listing_id = int(listing.listing.id or 0)
    now = datetime.now(timezone.utc)
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            signal_value=24.0,
            confidence_score=0.74,
            observed_at=now - timedelta(days=7),
            created_at=now - timedelta(days=7),
        )
    )
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            signal_value=33.0,
            confidence_score=0.82,
            observed_at=now,
            created_at=now,
        )
    )
    session.add(
        MarketTrend(
            owner_user_id=owner_user_id,
            trend_type="ASSET_SIGNAL_VALUE",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            trend_direction="UP",
            trend_strength=0.85,
            confidence_score=0.8,
            calculated_at=now,
            created_at=now,
        )
    )
    session.commit()


def test_market_forecast_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "market-forecast-owner@example.com"
    outsider_email = "market-forecast-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_forecast_inputs(session, owner_user_id=int(owner.id or 0))

    price_run = client.post("/api/v1/market-forecast/run/price", headers=auth_headers(owner_token))
    trends_run = client.post("/api/v1/market-forecast/run/trends", headers=auth_headers(owner_token))
    risk_run = client.post("/api/v1/market-forecast/run/risk", headers=auth_headers(owner_token))

    assert price_run.status_code == 201, price_run.text
    assert trends_run.status_code == 201, trends_run.text
    assert risk_run.status_code == 201, risk_run.text

    forecasts = client.get("/api/v1/market-forecast/forecasts?limit=100&offset=0", headers=auth_headers(owner_token))
    confidence = client.get("/api/v1/market-forecast/confidence?limit=100&offset=0", headers=auth_headers(owner_token))
    risks = client.get("/api/v1/market-forecast/risks?limit=100&offset=0", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/market-forecast/executions?limit=100&offset=0", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/market-forecast/forecasts?limit=100&offset=0", headers=auth_headers(outsider_token))

    assert forecasts.status_code == 200, forecasts.text
    assert confidence.status_code == 200, confidence.text
    assert risks.status_code == 200, risks.text
    assert executions.status_code == 200, executions.text
    assert forecasts.json()["data"]["items"]
    first_forecast_id = forecasts.json()["data"]["items"][0]["id"]
    detail = client.get(f"/api/v1/market-forecast/forecasts/{first_forecast_id}", headers=auth_headers(owner_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["forecast"]["id"] == first_forecast_id
    assert confidence.json()["data"]["items"]
    assert executions.json()["data"]["items"]
    assert outsider.json()["data"]["items"] == []
