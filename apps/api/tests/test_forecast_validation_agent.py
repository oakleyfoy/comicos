from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.forecast_validation_agent import run_forecast_validation_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_forecast_validation_agent_generates_validations_without_mutating_forecasts(client: TestClient) -> None:
    email = "forecast-validation-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Validation Listing",
                listing_description="validation seed",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="20.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        base_time = datetime.now(timezone.utc) - timedelta(days=2)
        forecast = MarketForecast(
            owner_user_id=owner_id,
            forecast_type="PRICE_FORECAST_30D",
            asset_type="marketplace_listing",
            asset_id=asset_id,
            forecast_horizon_days=30,
            forecast_value=25.0,
            confidence_score=0.8,
            created_at=base_time,
        )
        session.add(forecast)
        session.flush()
        session.add(
            MarketSignal(
                owner_user_id=owner_id,
                signal_type="FMV_SIGNAL",
                signal_source="inventory_fmv",
                asset_type="marketplace_listing",
                asset_id=asset_id,
                signal_value=20.0,
                confidence_score=0.75,
                observed_at=base_time + timedelta(days=1),
                created_at=base_time + timedelta(days=1),
            )
        )
        session.commit()

        before_value = float(session.get(MarketForecast, int(forecast.id or 0)).forecast_value)
        response = run_forecast_validation_agent(session, owner_user_id=owner_id)
        after_value = float(session.get(MarketForecast, int(forecast.id or 0)).forecast_value)

        assert response.execution.status == "COMPLETED"
        assert response.validations
        assert response.accuracy_metrics
        assert response.validations[0].variance_value == -5.0
        assert before_value == after_value
