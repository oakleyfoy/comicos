from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import (
    DealerOpportunityScore,
    DealerRecommendation,
    ForecastValidation,
    MarketForecast,
    MarketSignal,
    User,
)
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing
from test_inventory import auth_headers, register_and_login


def _seed_dashboard_inputs(session: Session, *, owner_user_id: int) -> None:
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Validation Dashboard Listing",
            listing_description="dashboard seed",
            listing_type="SINGLE_ISSUE",
            condition_label="VF",
            asking_price="18.00",
            currency="USD",
            quantity=1,
        ),
    )
    asset_id = int(listing.listing.id or 0)
    base_time = datetime.now(timezone.utc) - timedelta(days=2)
    forecast = MarketForecast(
        owner_user_id=owner_user_id,
        forecast_type="PRICE_FORECAST_30D",
        asset_type="marketplace_listing",
        asset_id=asset_id,
        forecast_horizon_days=30,
        forecast_value=24.0,
        confidence_score=0.8,
        created_at=base_time,
    )
    session.add(forecast)
    session.flush()
    session.add(MarketSignal(owner_user_id=owner_user_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=18.0, confidence_score=0.74, observed_at=base_time + timedelta(days=1), created_at=base_time + timedelta(days=1)))
    session.add(ForecastValidation(owner_user_id=owner_user_id, forecast_id=int(forecast.id or 0), validation_type="ACTUAL_SIGNAL_COMPARISON", predicted_value=24.0, actual_value=18.0, variance_value=-6.0, variance_percent=-25.0, validated_at=base_time + timedelta(days=1)))
    session.add(DealerRecommendation(owner_user_id=owner_user_id, recommendation_type="WATCH", asset_type="marketplace_listing", asset_id=asset_id, title="Monitor demand increase", description="Advisory watch signal.", confidence_score=0.65, priority_score=0.61, recommendation_status="OPEN", created_at=base_time))
    session.add(DealerOpportunityScore(owner_user_id=owner_user_id, asset_type="marketplace_listing", asset_id=asset_id, opportunity_score=0.58, risk_score=0.32, forecast_score=0.62, demand_score=0.6, grading_score=0.42, calculated_at=base_time + timedelta(days=1)))
    session.commit()


def test_forecast_validation_dashboard_routes_return_summary_and_lists(client: TestClient) -> None:
    owner_email = "forecast-validation-dashboard-owner@example.com"
    outsider_email = "forecast-validation-dashboard-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_dashboard_inputs(session, owner_user_id=int(owner.id or 0))

    client.post("/api/v1/forecast-validation/run/validation", headers=auth_headers(owner_token))
    client.post("/api/v1/forecast-validation/run/learning", headers=auth_headers(owner_token))
    client.post("/api/v1/forecast-validation/run/reliability", headers=auth_headers(owner_token))

    dashboard = client.get("/api/v1/forecast-validation-dashboard", headers=auth_headers(owner_token))
    accuracy = client.get("/api/v1/forecast-validation-dashboard/accuracy", headers=auth_headers(owner_token))
    drift = client.get("/api/v1/forecast-validation-dashboard/drift", headers=auth_headers(owner_token))
    signal_quality = client.get("/api/v1/forecast-validation-dashboard/signal-quality", headers=auth_headers(owner_token))
    outcomes = client.get("/api/v1/forecast-validation-dashboard/outcomes", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/forecast-validation-dashboard", headers=auth_headers(outsider_token))

    assert dashboard.status_code == 200, dashboard.text
    assert accuracy.status_code == 200, accuracy.text
    assert drift.status_code == 200, drift.text
    assert signal_quality.status_code == 200, signal_quality.text
    assert outcomes.status_code == 200, outcomes.text

    assert dashboard.json()["data"]["summary"]["total_validations"] >= 1
    assert "learning_trends" in dashboard.json()["data"]
    assert accuracy.json()["data"]["items"] is not None
    assert drift.json()["data"]["items"] is not None
    assert signal_quality.json()["data"]["items"] is not None
    assert outcomes.json()["data"]["items"] is not None
    assert outsider.json()["data"]["summary"]["total_validations"] == 0
