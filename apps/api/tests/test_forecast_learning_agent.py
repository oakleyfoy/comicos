from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import (
    DealerOpportunityScore,
    DealerRecommendation,
    ForecastValidation,
    MarketForecast,
    User,
)
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.forecast_learning_agent import run_forecast_learning_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_forecast_learning_agent_tracks_outcomes_without_mutating_recommendations(client: TestClient) -> None:
    email = "forecast-learning-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Learning Listing",
                listing_description="learning seed",
                listing_type="SINGLE_ISSUE",
                condition_label="NM",
                asking_price="30.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        now = datetime.now(timezone.utc)
        forecast = MarketForecast(
            owner_user_id=owner_id,
            forecast_type="PRICE_FORECAST_30D",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            forecast_horizon_days=30,
            forecast_value=35.0,
            confidence_score=0.82,
            created_at=now,
        )
        session.add(forecast)
        session.flush()
        session.add(
            ForecastValidation(
                owner_user_id=owner_id,
                forecast_id=int(forecast.id or 0),
                validation_type="ACTUAL_SIGNAL_COMPARISON",
                predicted_value=35.0,
                actual_value=32.0,
                variance_value=-3.0,
                variance_percent=-8.5714,
                validated_at=now,
            )
        )
        recommendation = DealerRecommendation(
            owner_user_id=owner_id,
            recommendation_type="BUY",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            title="Acquire additional copies",
            description="Advisory buy signal.",
            confidence_score=0.76,
            priority_score=0.84,
            recommendation_status="OPEN",
            created_at=now,
        )
        session.add(recommendation)
        session.add(
            DealerOpportunityScore(
                owner_user_id=owner_id,
                asset_type="marketplace_listing",
                asset_id=asset_id,
                opportunity_score=0.81,
                risk_score=0.21,
                forecast_score=0.79,
                demand_score=0.74,
                grading_score=0.62,
                calculated_at=now,
            )
        )
        session.commit()

        recommendation_count_before = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())
        response = run_forecast_learning_agent(session, owner_user_id=owner_id)
        recommendation_count_after = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_id)).all())

        assert response.execution.status == "COMPLETED"
        assert len(response.outcomes) >= 2
        assert any(row.forecast_id is not None for row in response.outcomes)
        assert any(row.recommendation_id is not None for row in response.outcomes)
        assert recommendation_count_before == recommendation_count_after
