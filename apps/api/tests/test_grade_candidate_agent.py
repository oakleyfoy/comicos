from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.dealer_copilot_engine import calculate_opportunity_scores, recommendation_detail
from app.services.grade_candidate_agent import run_grade_candidate_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_grade_candidate_agent_generates_advisory_grade_recommendation(client: TestClient) -> None:
    email = "dealer-grade@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Grade Candidate",
                listing_description="grade candidate",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="32.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        now = datetime.now(timezone.utc)
        session.add(MarketSignal(owner_user_id=owner_id, signal_type="SCAN_SIGNAL", signal_source="scan_agent", asset_type="marketplace_listing", asset_id=asset_id, signal_value=9.0, confidence_score=0.86, observed_at=now, created_at=now))
        session.add(MarketForecast(owner_user_id=owner_id, forecast_type="BULLISH_GRADE_FORECAST", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=40.0, confidence_score=0.83, created_at=now))
        session.add(MarketRiskAssessment(owner_user_id=owner_id, asset_type="marketplace_listing", asset_id=asset_id, risk_type="HIGH_VOLATILITY_RISK", risk_score=1.5, confidence_score=0.7, created_at=now))
        session.commit()
        calculate_opportunity_scores(session, owner_user_id=owner_id)
        response = run_grade_candidate_agent(session, owner_user_id=owner_id)

        assert response.executions[0].status == "COMPLETED"
        assert response.recommendations
        assert response.recommendations[0].recommendation_type == "GRADE"
        assert "submission" not in response.recommendations[0].description.lower()
        assert recommendation_detail(session, recommendation_id=response.recommendations[0].id).evidence
