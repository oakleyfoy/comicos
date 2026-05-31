from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ForecastValidation, MarketForecast, MarketSignal, User
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.forecast_reliability_agent import run_forecast_reliability_agent
from app.services.marketplace_listings import create_listing
from test_inventory import register_and_login


def test_forecast_reliability_agent_detects_drift_and_signal_quality(client: TestClient) -> None:
    email = "forecast-reliability-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        listing = create_listing(
            session,
            owner_id=owner_id,
            payload=MarketplaceListingCreate(
                listing_title="Reliability Listing",
                listing_description="reliability seed",
                listing_type="SINGLE_ISSUE",
                condition_label="VF",
                asking_price="16.00",
                currency="USD",
                quantity=1,
            ),
        )
        asset_id = int(listing.listing.id or 0)
        base_time = datetime.now(timezone.utc) - timedelta(days=3)
        forecasts = [
            MarketForecast(owner_user_id=owner_id, forecast_type="PRICE_FORECAST_30D", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=20.0, confidence_score=0.8, created_at=base_time),
            MarketForecast(owner_user_id=owner_id, forecast_type="PRICE_FORECAST_30D", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=28.0, confidence_score=0.82, created_at=base_time + timedelta(days=1)),
            MarketForecast(owner_user_id=owner_id, forecast_type="PRICE_FORECAST_30D", asset_type="marketplace_listing", asset_id=asset_id, forecast_horizon_days=30, forecast_value=40.0, confidence_score=0.85, created_at=base_time + timedelta(days=2)),
        ]
        for row in forecasts:
            session.add(row)
        session.flush()
        session.add(ForecastValidation(owner_user_id=owner_id, forecast_id=int(forecasts[-1].id or 0), validation_type="ACTUAL_SIGNAL_COMPARISON", predicted_value=40.0, actual_value=20.0, variance_value=-20.0, variance_percent=-50.0, validated_at=base_time + timedelta(days=2)))
        for index, value in enumerate([10.0, 35.0, 14.0, 31.0], start=1):
            session.add(
                MarketSignal(
                    owner_user_id=owner_id,
                    signal_type="FMV_SIGNAL",
                    signal_source="inventory_fmv",
                    asset_type="marketplace_listing",
                    asset_id=asset_id,
                    signal_value=value,
                    confidence_score=0.6 + (index * 0.05),
                    observed_at=base_time + timedelta(hours=index),
                    created_at=base_time + timedelta(hours=index),
                )
            )
        session.commit()

        forecast_values_before = [float(row.forecast_value) for row in session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all()]
        response = run_forecast_reliability_agent(session, owner_user_id=owner_id)
        forecast_values_after = [float(row.forecast_value) for row in session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all()]

        assert response.execution.status == "COMPLETED"
        assert response.drift_events
        assert response.signal_quality
        drift_types = {row.drift_type for row in response.drift_events}
        assert "FORECAST_DRIFT" in drift_types
        assert "SIGNAL_INSTABILITY" in drift_types
        assert "CONFIDENCE_FAILURE" in drift_types
        assert forecast_values_before == forecast_values_after
