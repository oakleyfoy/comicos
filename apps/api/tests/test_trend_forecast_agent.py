from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketForecast, MarketTrend, User
from app.services.trend_forecast_agent import run_trend_forecast_agent
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_trend_forecast_agent_generates_bullish_bearish_and_neutral_forecasts(client: TestClient) -> None:
    email = "trend-forecast-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = _owner_id(session, email)
        now = datetime.now(timezone.utc)
        session.add(
            MarketTrend(
                owner_user_id=owner_id,
                trend_type="ASSET_SIGNAL_VALUE",
                asset_type="marketplace_listing",
                asset_id=101,
                trend_direction="UP",
                trend_strength=0.8,
                confidence_score=0.84,
                calculated_at=now,
                created_at=now,
            )
        )
        session.add(
            MarketTrend(
                owner_user_id=owner_id,
                trend_type="ASSET_SIGNAL_VALUE",
                asset_type="marketplace_listing",
                asset_id=102,
                trend_direction="DOWN",
                trend_strength=0.7,
                confidence_score=0.78,
                calculated_at=now,
                created_at=now,
            )
        )
        session.add(
            MarketTrend(
                owner_user_id=owner_id,
                trend_type="MARKET_SCORE",
                asset_type="market",
                asset_id=None,
                trend_direction="FLAT",
                trend_strength=0.1,
                confidence_score=0.65,
                calculated_at=now,
                created_at=now,
            )
        )
        session.commit()

        result = run_trend_forecast_agent(session, owner_user_id=owner_id)
        forecasts = session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_id)).all()

        assert result.execution.status == "COMPLETED"
        assert result.created_count >= 3
        assert any("BULLISH" in row.forecast_type for row in forecasts)
        assert any("BEARISH" in row.forecast_type for row in forecasts)
        assert any("NEUTRAL" in row.forecast_type for row in forecasts)
        assert all("recommend" not in row.forecast_type.lower() for row in forecasts)
