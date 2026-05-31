from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.dealer_copilot_engine import calculate_opportunity_scores
from app.services.hold_agent import run_hold_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_hold_agent_generates_hold_recommendation(client: TestClient) -> None:
    email = "dealer-hold@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Hold Candidate",
                listing_description="hold candidate",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="18.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        now = datetime.now(timezone.utc)
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=18.0, confidence_score=0.45, observed_at=now, created_at=now))
        session.add(MarketForecast(owner_user_id=owner_id, forecast_type="NEUTRAL_PRICE_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=1.0, confidence_score=0.6, created_at=now))
        session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=4.0, confidence_score=0.6, created_at=now))
        session.commit()
        calculate_opportunity_scores(session, owner_user_id=owner_id)
        response = run_hold_agent(session, owner_user_id=owner_id)

        assert response.executions[0].status == "COMPLETED"
        assert response.recommendations
        assert response.recommendations[0].recommendation_type == "HOLD"
        assert "holding" in response.recommendations[0].title.lower() or "hold" in response.recommendations[0].title.lower()
