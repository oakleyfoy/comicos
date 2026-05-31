from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketObservation, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.dealer_copilot_engine import (
    build_copilot_summary,
    generate_recommendations,
    get_recommendation_for_owner,
)
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def _seed_asset(
    session: Session,
    *,
    owner_id: int,
    title: str,
    price: str,
    signal_confidence: float,
    forecast_type: str,
    forecast_value: float,
    risk_score: float,
) -> int:
    listing = create_listing(
        session,
        owner_id=owner_id,
        payload=MarketplaceListingCreate(
            listing_title=title,
            listing_description=f"{title} seed",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price=price,
            currency="USD",
            quantity=1,
        ),
    )
    asset_id = int(listing.listing.id or 0)
    now = datetime.now(timezone.utc)
    session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=20.0, confidence_score=signal_confidence, observed_at=now, created_at=now))
    session.add(MarketForecast(owner_user_id=owner_id, forecast_type=forecast_type, asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=forecast_value, confidence_score=max(signal_confidence, 0.6), created_at=now))
    session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=risk_score, confidence_score=0.72, created_at=now))
    return asset_id


def test_dealer_copilot_engine_scores_and_ranks_recommendations(client: TestClient) -> None:
    email = "dealer-engine@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        _seed_asset(session, owner_id=owner_id, title="Buy Asset", price="20.00", signal_confidence=0.82, forecast_type="BULLISH_TREND_FORECAST", forecast_value=35.0, risk_score=2.0)
        _seed_asset(session, owner_id=owner_id, title="Sell Asset", price="20.00", signal_confidence=0.64, forecast_type="BEARISH_TREND_FORECAST", forecast_value=-8.0, risk_score=8.0)
        _seed_asset(session, owner_id=owner_id, title="Hold Asset", price="20.00", signal_confidence=0.45, forecast_type="NEUTRAL_TREND_FORECAST", forecast_value=1.0, risk_score=4.0)
        session.add(MarketObservation(owner_user_id=owner_id, observation_uuid="dealer-engine-observation", observation_type="market", title="Market moving", description="Observation for watchlist", confidence_score=0.7, created_by_agent="market_observation_agent", created_at=datetime.now(timezone.utc)))
        session.commit()

        response = generate_recommendations(session, owner_user_id=owner_id)

        assert response.opportunities
        types = {row.recommendation_type for row in response.recommendations}
        assert {"BUY", "SELL", "HOLD", "GRADE", "WATCH"}.issubset(types)
        priorities = [row.priority_score for row in response.recommendations]
        assert priorities == sorted(priorities, reverse=True)
        detail = get_recommendation_for_owner(session, owner_user_id=owner_id, recommendation_id=response.recommendations[0].id)
        assert detail.evidence
        summary = build_copilot_summary(session, owner_user_id=owner_id)
        assert summary.total_recommendations >= 5
        assert summary.by_type["BUY"] >= 1
