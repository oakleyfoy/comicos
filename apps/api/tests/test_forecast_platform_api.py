from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import (
    DealerOpportunityScore,
    DealerRecommendation,
    MarketForecast,
    MarketObservation,
    MarketRiskAssessment,
    MarketSignal,
    MarketSnapshot,
    MarketTrend,
    User,
)
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.dealer_copilot_engine import create_recommendation_with_evidence
from app.services.forecast_learning_agent import run_forecast_learning_agent
from app.services.forecast_reliability_agent import run_forecast_reliability_agent
from app.services.forecast_validation_agent import run_forecast_validation_agent
from app.services.marketplace_listings import create_listing
from test_inventory import auth_headers, register_and_login


def _seed_api_platform(session: Session, *, owner_user_id: int) -> None:
    now = datetime.now(timezone.utc) - timedelta(days=2)
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="API Forecast Platform",
            listing_description="api seed",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="22.00",
            currency="USD",
            quantity=1,
        ),
    )
    asset_id = int(listing.listing.id or 0)
    session.add(MarketSignal(owner_user_id=owner_user_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=16.0, confidence_score=0.76, observed_at=now, created_at=now))
    session.add(MarketSignal(owner_user_id=owner_user_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=23.0, confidence_score=0.81, observed_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
    session.add(MarketSnapshot(owner_user_id=owner_user_id, snapshot_date=(now + timedelta(days=1)).date(), market_score=70.0, bullish_signals=3, bearish_signals=1, neutral_signals=1, created_at=now + timedelta(days=1)))
    session.add(MarketTrend(owner_user_id=owner_user_id, trend_type="ASSET_SIGNAL_VALUE", asset_type="marketplace_listing", asset_id=asset_id, trend_direction="UP", trend_strength=0.74, confidence_score=0.77, calculated_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
    session.add(MarketObservation(owner_user_id=owner_user_id, observation_uuid="forecast-platform-api-observation", observation_type="market", title="Healthy outlook", description="Bullish market posture.", confidence_score=0.76, created_by_agent="market_observation_agent", created_at=now + timedelta(days=1)))
    forecast = MarketForecast(owner_user_id=owner_user_id, forecast_type="BULLISH_TREND_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=25.0, confidence_score=0.82, created_at=now)
    session.add(forecast)
    session.add(MarketRiskAssessment(owner_user_id=owner_user_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=0.25, confidence_score=0.72, created_at=now + timedelta(days=1)))
    session.add(DealerOpportunityScore(owner_user_id=owner_user_id, asset_type="marketplace_listing", asset_id=asset_id, opportunity_score=0.77, risk_score=0.25, forecast_score=0.82, demand_score=0.73, grading_score=0.61, calculated_at=now + timedelta(days=1)))
    session.flush()
    create_recommendation_with_evidence(
        session,
        owner_user_id=owner_user_id,
        execution_id=None,
        recommendation_key=f"buy-api:{asset_id}",
        recommendation_type="BUY",
        asset_type="marketplace_listing",
        asset_id=asset_id,
        title="Acquire additional copies",
        description="Advisory buy signal.",
        confidence_score=0.81,
        priority_score=0.86,
        evidence=[{"evidence_type": "forecast_context", "evidence_source": "price_forecast_agent", "evidence_payload_json": {"forecast_id": int(forecast.id or 0)}, "evidence_score": 0.81}],
    )
    session.commit()
    run_forecast_validation_agent(session, owner_user_id=owner_user_id)
    run_forecast_reliability_agent(session, owner_user_id=owner_user_id)
    run_forecast_learning_agent(session, owner_user_id=owner_user_id)


def test_forecast_platform_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "forecast-platform-api-owner@example.com"
    outsider_email = "forecast-platform-api-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        _seed_api_platform(session, owner_user_id=int(owner.id or 0))
        forecast_count_before = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == int(owner.id or 0))).all())
        recommendation_count_before = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == int(owner.id or 0))).all())

    dashboard = client.get("/api/v1/forecast-platform", headers=auth_headers(owner_token))
    summary = client.get("/api/v1/forecast-platform/summary", headers=auth_headers(owner_token))
    health = client.get("/api/v1/forecast-platform/health", headers=auth_headers(owner_token))
    validation = client.get("/api/v1/forecast-platform/validation", headers=auth_headers(owner_token))
    certification = client.get("/api/v1/forecast-platform/certification", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/forecast-platform", headers=auth_headers(outsider_token))

    assert dashboard.status_code == 200, dashboard.text
    assert summary.status_code == 200, summary.text
    assert health.status_code == 200, health.text
    assert validation.status_code == 200, validation.text
    assert certification.status_code == 200, certification.text
    assert dashboard.json()["data"]["certification"]["platform_certified"] is True
    assert summary.json()["data"]["forecast_count"] >= 1
    assert len(health.json()["data"]["components"]) == 6
    assert len(validation.json()["data"]["checks"]) == 5
    assert outsider.json()["data"]["summary"]["forecast_count"] == 0

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == owner_email)).one()
        forecast_count_after = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == int(owner.id or 0))).all())
        recommendation_count_after = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == int(owner.id or 0))).all())

    assert forecast_count_before == forecast_count_after
    assert recommendation_count_before == recommendation_count_after
