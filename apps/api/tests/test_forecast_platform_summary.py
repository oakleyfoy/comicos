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
from app.services.forecast_platform_summary import get_forecast_platform_certification, get_forecast_platform_summary
from app.services.forecast_reliability_agent import run_forecast_reliability_agent
from app.services.forecast_validation_agent import run_forecast_validation_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_forecast_platform_summary_aggregates_and_certifies(client: TestClient) -> None:
    email = "forecast-platform-summary@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        now = datetime.now(timezone.utc) - timedelta(days=2)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Summary Listing",
                listing_description="summary seed",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="20.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=18.0, confidence_score=0.78, observed_at=now, created_at=now))
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=26.0, confidence_score=0.83, observed_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
        session.add(MarketSnapshot(owner_user_id=owner_id, snapshot_date=(now + timedelta(days=1)).date(), market_score=74.0, bullish_signals=4, bearish_signals=1, neutral_signals=1, created_at=now + timedelta(days=1)))
        session.add(MarketTrend(owner_user_id=owner_id, trend_type="ASSET_SIGNAL_VALUE", asset_type="marketplace_listing", asset_id=asset_id, trend_direction="UP", trend_strength=0.8, confidence_score=0.79, calculated_at=now + timedelta(days=1), created_at=now + timedelta(days=1)))
        session.add(MarketObservation(owner_user_id=owner_id, observation_uuid="forecast-platform-summary-observation", observation_type="market", title="Strong outlook", description="Bullish posture.", confidence_score=0.8, created_by_agent="market_observation_agent", created_at=now + timedelta(days=1)))
        bullish = MarketForecast(owner_user_id=owner_id, forecast_type="BULLISH_TREND_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=28.0, confidence_score=0.84, created_at=now)
        bearish = MarketForecast(owner_user_id=owner_id, forecast_type="BEARISH_TREND_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=-4.0, confidence_score=0.67, created_at=now + timedelta(hours=1))
        session.add(bullish)
        session.add(bearish)
        session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=0.31, confidence_score=0.72, created_at=now + timedelta(days=1)))
        session.add(DealerOpportunityScore(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, opportunity_score=0.79, risk_score=0.31, forecast_score=0.84, demand_score=0.76, grading_score=0.68, calculated_at=now + timedelta(days=1)))
        session.flush()
        create_recommendation_with_evidence(
            session,
            owner_user_id=owner_id,
            execution_id=None,
            recommendation_key=f"buy-summary:{asset_id}",
            recommendation_type="BUY",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            title="Acquire additional copies",
            description="Advisory buy signal.",
            confidence_score=0.83,
            priority_score=0.88,
            evidence=[{"evidence_type": "forecast_context", "evidence_source": "price_forecast_agent", "evidence_payload_json": {"forecast_id": int(bullish.id or 0)}, "evidence_score": 0.83}],
        )
        create_recommendation_with_evidence(
            session,
            owner_user_id=owner_id,
            execution_id=None,
            recommendation_key=f"grade-summary:{asset_id}",
            recommendation_type="GRADE",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            title="Strong grading candidate",
            description="Advisory grade signal.",
            confidence_score=0.74,
            priority_score=0.7,
            evidence=[{"evidence_type": "grading_score", "evidence_source": "dealer_copilot_engine", "evidence_payload_json": {"asset_id": asset_id}, "evidence_score": 0.74}],
        )
        session.commit()
        run_forecast_validation_agent(session, owner_user_id=owner_id)
        run_forecast_reliability_agent(session, owner_user_id=owner_id)
        run_forecast_learning_agent(session, owner_user_id=owner_id)
        forecast_count_before = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all())
        recommendation_count_before = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())
        summary = get_forecast_platform_summary(session, owner_user_id=owner_id)
        certification = get_forecast_platform_certification(session, owner_user_id=owner_id)
        forecast_count_after = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all())
        recommendation_count_after = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())

        assert summary.market_score == 74.0
        assert summary.forecast_count >= 2
        assert summary.risk_count >= 1
        assert summary.recommendation_count >= 2
        assert summary.top_buy_recommendations
        assert summary.top_grade_candidates
        assert certification.platform_certified is True
        assert forecast_count_before == forecast_count_after
        assert recommendation_count_before == recommendation_count_after
