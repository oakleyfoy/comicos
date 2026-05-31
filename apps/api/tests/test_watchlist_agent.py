from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketObservation, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.dealer_copilot_engine import calculate_opportunity_scores
from app.services.marketplace_listings import create_listing
from app.services.watchlist_agent import run_watchlist_agent
from test_inventory import register_and_login


def test_watchlist_agent_generates_watch_recommendation(client: TestClient) -> None:
    email = "dealer-watch@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Watch Candidate",
                listing_description="watch candidate",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="14.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        now = datetime.now(timezone.utc)
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="DEMAND_SIGNAL", signal_source="market_signal_agent", asset_type="marketplace_listing", asset_id=asset_id, signal_value=10.0, confidence_score=0.55, observed_at=now, created_at=now))
        session.add(MarketForecast(owner_user_id=owner_id, forecast_type="NEUTRAL_TREND_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=2.0, confidence_score=0.62, created_at=now))
        session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="WEAK_DEMAND_RISK", risk_score=3.5, confidence_score=0.65, created_at=now))
        session.add(MarketObservation(owner_user_id=owner_id, observation_uuid="watch-obs-1", observation_type="demand", title="Demand uptick", description="Demand is rising.", confidence_score=0.72, created_by_agent="market_observation_agent", created_at=now))
        session.commit()
        calculate_opportunity_scores(session, owner_user_id=owner_id)
        response = run_watchlist_agent(session, owner_user_id=owner_id)

        assert response.executions[0].status == "COMPLETED"
        assert response.recommendations
        assert response.recommendations[0].recommendation_type == "WATCH"
        assert "monitor" in response.recommendations[0].title.lower()
