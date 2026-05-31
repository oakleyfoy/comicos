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


def _seed_validation_api_inputs(session: Session, *, owner_user_id: int) -> None:
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Validation API Listing",
            listing_description="validation api seed",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="24.00",
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
        forecast_value=30.0,
        confidence_score=0.82,
        created_at=base_time,
    )
    session.add(forecast)
    session.flush()
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            signal_value=22.0,
            confidence_score=0.77,
            observed_at=base_time + timedelta(days=1),
            created_at=base_time + timedelta(days=1),
        )
    )
    session.add(
        ForecastValidation(
            owner_user_id=owner_user_id,
            forecast_id=int(forecast.id or 0),
            validation_type="ACTUAL_SIGNAL_COMPARISON",
            predicted_value=30.0,
            actual_value=22.0,
            variance_value=-8.0,
            variance_percent=-26.6667,
            validated_at=base_time + timedelta(days=1),
        )
    )
    recommendation = DealerRecommendation(
        owner_user_id=owner_user_id,
        recommendation_type="BUY",
        asset_type="marketplace_listing",
        asset_id=asset_id,
        title="Acquire additional copies",
        description="Advisory buy signal.",
        confidence_score=0.76,
        priority_score=0.84,
        recommendation_status="OPEN",
        created_at=base_time,
    )
    session.add(recommendation)
    session.add(
        DealerOpportunityScore(
            owner_user_id=owner_user_id,
            asset_type="marketplace_listing",
            asset_id=asset_id,
            opportunity_score=0.8,
            risk_score=0.22,
            forecast_score=0.81,
            demand_score=0.74,
            grading_score=0.63,
            calculated_at=base_time + timedelta(days=1),
        )
    )
    session.commit()


def test_forecast_validation_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "forecast-validation-owner@example.com"
    outsider_email = "forecast-validation-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_validation_api_inputs(session, owner_user_id=int(owner.id or 0))
        forecast_count_before = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == int(owner.id or 0))).all())
        recommendation_count_before = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == int(owner.id or 0))).all())

    validation_run = client.post("/api/v1/forecast-validation/run/validation", headers=auth_headers(owner_token))
    learning_run = client.post("/api/v1/forecast-validation/run/learning", headers=auth_headers(owner_token))
    reliability_run = client.post("/api/v1/forecast-validation/run/reliability", headers=auth_headers(owner_token))

    assert validation_run.status_code == 201, validation_run.text
    assert learning_run.status_code == 201, learning_run.text
    assert reliability_run.status_code == 201, reliability_run.text

    accuracy = client.get("/api/v1/forecast-validation/accuracy?limit=100&offset=0", headers=auth_headers(owner_token))
    drift = client.get("/api/v1/forecast-validation/drift?limit=100&offset=0", headers=auth_headers(owner_token))
    signal_quality = client.get("/api/v1/forecast-validation/signal-quality?limit=100&offset=0", headers=auth_headers(owner_token))
    outcomes = client.get("/api/v1/forecast-validation/outcomes?limit=100&offset=0", headers=auth_headers(owner_token))
    executions = client.get("/api/v1/forecast-validation/executions?limit=100&offset=0", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/forecast-validation/accuracy?limit=100&offset=0", headers=auth_headers(outsider_token))

    assert accuracy.status_code == 200, accuracy.text
    assert drift.status_code == 200, drift.text
    assert signal_quality.status_code == 200, signal_quality.text
    assert outcomes.status_code == 200, outcomes.text
    assert executions.status_code == 200, executions.text
    assert accuracy.json()["data"]["items"]
    assert outcomes.json()["data"]["items"]
    assert executions.json()["data"]["items"]
    assert outsider.json()["data"]["items"] == []

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        forecast_count_after = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == int(owner.id or 0))).all())
        recommendation_count_after = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == int(owner.id or 0))).all())

    assert forecast_count_before == forecast_count_after
    assert recommendation_count_before == recommendation_count_after
