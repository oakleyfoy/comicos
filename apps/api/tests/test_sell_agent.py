from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.dealer_copilot_engine import calculate_opportunity_scores, recommendation_detail
from app.services.marketplace_listings import create_listing
from app.services.sell_agent import run_sell_agent
from test_inventory import register_and_login


def test_sell_agent_generates_advisory_sell_signal(client: TestClient) -> None:
    email = "dealer-sell@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Sell Candidate",
                listing_description="sell candidate",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="45.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        now = datetime.now(timezone.utc)
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="FMV_SIGNAL", signal_source="inventory_fmv", asset_type="marketplace_listing", asset_id=asset_id, signal_value=45.0, confidence_score=0.65, observed_at=now, created_at=now))
        session.add(MarketForecast(owner_user_id=owner_id, forecast_type="BEARISH_TREND_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=-5.0, confidence_score=0.8, created_at=now))
        session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="RAPID_PRICE_DECLINE_RISK", risk_score=8.0, confidence_score=0.85, created_at=now))
        session.commit()
        calculate_opportunity_scores(session, owner_user_id=owner_id)
        response = run_sell_agent(session, owner_user_id=owner_id)

        assert response.executions[0].status == "COMPLETED"
        assert response.recommendations
        recommendation = response.recommendations[0]
        assert recommendation.recommendation_type == "SELL"
        assert "listing changes" not in recommendation.description.lower()
        assert recommendation_detail(session, recommendation_id=recommendation.id).evidence
