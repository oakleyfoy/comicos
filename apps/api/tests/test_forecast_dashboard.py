from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketSignal, MarketTrend, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing
from test_inventory import auth_headers, register_and_login


def _seed_forecast_dashboard_inputs(session: Session, *, owner_user_id: int) -> None:
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Forecast Dashboard Listing",
            listing_description="Forecast dashboard seed",
            listing_type="SINGLE_ISSUE",
            condition_label="VF",
            asking_price="18.00",
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
            signal_value=14.0,
            confidence_score=0.7,
            observed_at=now - timedelta(days=5),
            created_at=now - timedelta(days=5),
        )
    )
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            signal_value=21.0,
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
            trend_direction="DOWN",
            trend_strength=0.88,
            confidence_score=0.79,
            calculated_at=now,
            created_at=now,
        )
    )
    session.commit()


def test_forecast_dashboard_routes_return_summary_and_lists(client: TestClient) -> None:
    owner_email = "forecast-dashboard-owner@example.com"
    outsider_email = "forecast-dashboard-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_forecast_dashboard_inputs(session, owner_user_id=int(owner.id or 0))

    client.post("/api/v1/market-forecast/run/price", headers=auth_headers(owner_token))
    client.post("/api/v1/market-forecast/run/trends", headers=auth_headers(owner_token))
    client.post("/api/v1/market-forecast/run/risk", headers=auth_headers(owner_token))

    dashboard = client.get("/api/v1/forecast-dashboard", headers=auth_headers(owner_token))
    summary = client.get("/api/v1/forecast-dashboard/summary", headers=auth_headers(owner_token))
    bullish = client.get("/api/v1/forecast-dashboard/bullish", headers=auth_headers(owner_token))
    bearish = client.get("/api/v1/forecast-dashboard/bearish", headers=auth_headers(owner_token))
    risk = client.get("/api/v1/forecast-dashboard/risk", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/forecast-dashboard", headers=auth_headers(outsider_token))

    assert dashboard.status_code == 200, dashboard.text
    assert summary.status_code == 200, summary.text
    assert bullish.status_code == 200, bullish.text
    assert bearish.status_code == 200, bearish.text
    assert risk.status_code == 200, risk.text

    assert dashboard.json()["data"]["summary"]["total_forecasts"] >= 1
    assert "top_bullish_forecasts" in dashboard.json()["data"]
    assert "highest_risk_assets" in dashboard.json()["data"]
    assert summary.json()["data"]["average_confidence_score"] >= 0
    assert risk.json()["data"]["items"] is not None
    assert outsider.json()["data"]["summary"]["total_forecasts"] == 0
