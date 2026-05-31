from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import (
    DealerRecommendation,
    MarketAgentExecution,
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
from app.services.forecast_platform_health import get_forecast_platform_health
from app.services.forecast_reliability_agent import run_forecast_reliability_agent
from app.services.forecast_validation_agent import run_forecast_validation_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_forecast_platform_health_returns_component_statuses_without_mutation(client: TestClient) -> None:
    email = "forecast-platform-health@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        now = datetime.now(timezone.utc) - timedelta(days=2)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Health Listing",
                listing_description="health seed",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="18.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=15.0, confidence_score=0.74, observed_at=now, created_at=now))
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=21.0, confidence_score=0.8, observed_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
        session.add(MarketSnapshot(owner_user_id=owner_id, snapshot_date=(now + timedelta(days=1)).date(), market_score=68.0, bullish_signals=3, bearish_signals=1, neutral_signals=1, created_at=now + timedelta(days=1)))
        session.add(MarketTrend(owner_user_id=owner_id, trend_type="ASSET_SIGNAL_VALUE", asset_type="marketplace_listing", asset_id=asset_id, trend_direction="UP", trend_strength=0.72, confidence_score=0.75, calculated_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
        session.add(MarketObservation(owner_user_id=owner_id, observation_uuid="forecast-platform-health-observation", observation_type="market", title="Healthy signal posture", description="Signals look good.", confidence_score=0.7, created_by_agent="market_observation_agent", created_at=now + timedelta(days=1)))
        session.add(MarketAgentExecution(owner_user_id=owner_id, agent_code="market_signal_agent", status="COMPLETED", started_at=now, completed_at=now + timedelta(minutes=1), duration_ms=60000, created_at=now))
        forecast = MarketForecast(owner_user_id=owner_id, forecast_type="PRICE_FORECAST_30D", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=20.0, confidence_score=0.79, created_at=now)
        session.add(forecast)
        session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=0.22, confidence_score=0.7, created_at=now + timedelta(days=1)))
        session.flush()
        create_recommendation_with_evidence(
            session,
            owner_user_id=owner_id,
            execution_id=None,
            recommendation_key=f"buy-health:{asset_id}",
            recommendation_type="BUY",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            title="Acquire additional copies",
            description="Advisory buy signal.",
            confidence_score=0.8,
            priority_score=0.84,
            evidence=[{"evidence_type": "opportunity_score", "evidence_source": "dealer_copilot_engine", "evidence_payload_json": {"asset_id": asset_id}, "evidence_score": 0.8}],
        )
        session.commit()
        run_forecast_validation_agent(session, owner_user_id=owner_id)
        run_forecast_reliability_agent(session, owner_user_id=owner_id)
        run_forecast_learning_agent(session, owner_user_id=owner_id)
        forecast_count_before = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all())
        recommendation_count_before = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())
        health = get_forecast_platform_health(session, owner_user_id=owner_id)
        forecast_count_after = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all())
        recommendation_count_after = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())

        assert health.overall_status in {"HEALTHY", "WARNING"}
        assert len(health.components) == 6
        assert any(component.component_code == "dealer_copilot_health" for component in health.components)
        assert forecast_count_before == forecast_count_after
        assert recommendation_count_before == recommendation_count_after
