from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import (
    MarketForecast,
    MarketForecastConfidence,
    MarketSignal,
    MarketTrend,
    User,
)
from app.schemas.marketplace_listing import MarketplaceListingCreate
from app.services.marketplace_listings import create_listing
from app.services.price_forecast_agent import (
    generate_30_day_forecast,
    generate_90_day_forecast,
    generate_180_day_forecast,
)
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_price_inputs(session: Session, *, owner_user_id: int) -> int:
    listing = create_listing(
        session,
        owner_id=owner_user_id,
        payload=MarketplaceListingCreate(
            listing_title="Forecast Price Listing",
            listing_description="Forecast test listing",
            listing_type="SINGLE_ISSUE",
            condition_label="NM",
            asking_price="25.00",
            currency="USD",
            quantity=1,
        ),
    )
    listing_id = int(listing.listing.id)
    second_observed = datetime.now(timezone.utc)
    first_observed = second_observed - timedelta(days=7)
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            signal_value=20.0,
            confidence_score=0.7,
            observed_at=first_observed,
            created_at=first_observed,
        )
    )
    session.add(
        MarketSignal(
            owner_user_id=owner_user_id,
            signal_type="FMV_SIGNAL",
            signal_source="inventory_fmv",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            signal_value=28.0,
            confidence_score=0.8,
            observed_at=second_observed,
            created_at=second_observed,
        )
    )
    session.add(
        MarketTrend(
            owner_user_id=owner_user_id,
            trend_type="ASSET_SIGNAL_VALUE",
            asset_type="marketplace_listing",
            asset_id=listing_id,
            trend_direction="UP",
            trend_strength=0.9,
            confidence_score=0.82,
            calculated_at=second_observed,
            created_at=second_observed,
        )
    )
    session.commit()
    return listing_id


def test_price_forecast_agent_generates_30_90_180_and_retains_history(client: TestClient) -> None:
    email = "price-forecast-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = _owner_id(session, email)
        _seed_price_inputs(session, owner_user_id=owner_id)

        first_30 = generate_30_day_forecast(session, owner_user_id=owner_id)
        first_90 = generate_90_day_forecast(session, owner_user_id=owner_id)
        first_180 = generate_180_day_forecast(session, owner_user_id=owner_id)
        second_30 = generate_30_day_forecast(session, owner_user_id=owner_id)
        session.commit()

        forecasts = session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all()
        confidence = session.exec(select(MarketForecastConfidence)).all()

        assert first_30 and first_90 and first_180
        assert len(forecasts) == len(first_30) + len(first_90) + len(first_180) + len(second_30)
        assert len(confidence) == len(forecasts)
        assert {row.forecast_horizon_days for row in forecasts} >= {30, 90, 180}
        assert all("recommend" not in row.forecast_type.lower() for row in forecasts)
        assert all(row.confidence_score > 0 for row in forecasts)
