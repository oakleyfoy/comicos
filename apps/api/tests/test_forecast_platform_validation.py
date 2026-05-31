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
from app.services.forecast_platform_validation import validate_forecast_platform
from app.services.forecast_reliability_agent import run_forecast_reliability_agent
from app.services.forecast_validation_agent import run_forecast_validation_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def _seed_certified_platform(session: Session, *, owner_user_id: int) -> None:
    now = datetime.now(timezone.utc) - timedelta(days=2)
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Forecast Platform Seed",
            listing_description="closeout seed",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="30.00",
            currency="USD",
            quantity=1,
        ),
    )
    asset_id = int(listing.listing.id or 0)
    session.add(MarketSignal(owner_user_id=owner_user_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=22.0, confidence_score=0.8, observed_at=now, created_at=now))
    session.add(MarketSignal(owner_user_id=owner_user_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=28.0, confidence_score=0.84, observed_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
    session.add(MarketSnapshot(owner_user_id=owner_user_id, snapshot_date=(now + timedelta(days=1)).date(), market_score=72.0, bullish_signals=4, bearish_signals=1, neutral_signals=1, created_at=now + timedelta(days=1)))
    session.add(MarketTrend(owner_user_id=owner_user_id, trend_type="ASSET_SIGNAL_VALUE", asset_type="marketplace_listing", asset_id=asset_id, trend_direction="UP", trend_strength=0.82, confidence_score=0.79, calculated_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
    session.add(MarketObservation(owner_user_id=owner_user_id, observation_uuid="forecast-platform-observation", observation_type="market", title="Bullish market posture", description="Signals and trend align.", confidence_score=0.77, created_by_agent="market_observation_agent", created_at=now + timedelta(days=1)))
    forecast = MarketForecast(owner_user_id=owner_user_id, forecast_type="PRICE_FORECAST_30D", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=27.0, confidence_score=0.81, created_at=now)
    session.add(forecast)
    session.add(MarketRiskAssessment(owner_user_id=owner_user_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=0.18, confidence_score=0.7, created_at=now + timedelta(days=1)))
    session.add(DealerOpportunityScore(owner_user_id=owner_user_id, asset_type="marketplace_listing", asset_id=asset_id, opportunity_score=0.82, risk_score=0.18, forecast_score=0.81, demand_score=0.78, grading_score=0.64, calculated_at=now + timedelta(days=1)))
    session.flush()
    create_recommendation_with_evidence(
        session,
        owner_user_id=owner_user_id,
        execution_id=None,
        recommendation_key=f"buy:{asset_id}",
        recommendation_type="BUY",
        asset_type="marketplace_listing",
        asset_id=asset_id,
        title="Acquire additional copies",
        description="Advisory buy signal.",
        confidence_score=0.82,
        priority_score=0.88,
        evidence=[{"evidence_type": "forecast_context", "evidence_source": "price_forecast_agent", "evidence_payload_json": {"forecast_id": int(forecast.id or 0)}, "evidence_score": 0.82}],
    )
    session.commit()
    run_forecast_validation_agent(session, owner_user_id=owner_user_id)
    run_forecast_reliability_agent(session, owner_user_id=owner_user_id)


def test_forecast_platform_validation_returns_pass_without_mutation(client: TestClient) -> None:
    email = "forecast-platform-validation@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        _seed_certified_platform(session, owner_user_id=owner_id)
        forecast_count_before = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all())
        recommendation_count_before = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())
        validation = validate_forecast_platform(session, owner_user_id=owner_id)
        forecast_count_after = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all())
        recommendation_count_after = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())

        assert validation.overall_status == "PASS"
        assert validation.platform_certified is True
        assert len(validation.checks) == 5
        assert forecast_count_before == forecast_count_after
        assert recommendation_count_before == recommendation_count_after
