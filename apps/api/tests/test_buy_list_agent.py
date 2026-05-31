from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketRiskAssessment, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.buy_list_agent import run_buy_list_agent
from app.services.dealer_copilot_engine import calculate_opportunity_scores, recommendation_detail
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def _seed_buy_candidate(session: Session, *, owner_user_id: int) -> int:
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Buy Candidate",
            listing_description="buy candidate",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="20.00",
            currency="USD",
            quantity=1,
        ),
    )
    asset_id = int(listing.listing.id or 0)
    now = datetime.now(timezone.utc)
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            signal_value=28.0,
            confidence_score=0.82,
            observed_at=now,
            created_at=now,
        )
    )
    session.add(
        MarketForecast(
            owner_user_id=owner_user_id,
            forecast_type="BULLISH_TREND_FORECAST",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            forecast_horizon_days=30,
            forecast_value=35.0,
            confidence_score=0.84,
            created_at=now,
        )
    )
    session.add(
        MarketRiskAssessment(
            owner_user_id=owner_user_id,
            asset_type="marketplace_listing",
            asset_id=asset_id,
            risk_type="HIGH_VOLATILITY_RISK",
            risk_score=2.0,
            confidence_score=0.7,
            created_at=now,
        )
    )
    session.commit()
    return asset_id


def test_buy_list_agent_generates_evidence_backed_recommendation(client: TestClient) -> None:
    email = "dealer-buy@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        asset_id = _seed_buy_candidate(session, owner_user_id=owner_id)
        calculate_opportunity_scores(session, owner_user_id=owner_id)
        response = run_buy_list_agent(session, owner_user_id=owner_id)

        assert response.executions[0].status == "COMPLETED"
        assert response.recommendations
        recommendation = response.recommendations[0]
        assert recommendation.recommendation_type == "BUY"
        assert recommendation.asset_id == asset_id
        assert "purchase" not in recommendation.description.lower()
        detail = recommendation_detail(session, recommendation_id=recommendation.id)
        assert len(detail.evidence) >= 1
