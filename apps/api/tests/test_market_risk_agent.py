from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import MarketRiskAssessment, MarketSignal, MarketSnapshot, MarketTrend, User
from app.services.market_risk_agent import run_market_risk_agent
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_market_risk_agent_generates_risks_without_recommendations(client: TestClient) -> None:
    email = "market-risk-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = _owner_id(session, email)
        now = datetime.now(timezone.utc)
        session.add(
            MarketSignal(
                owner_user_id=owner_id,
                signal_type="FMV_SIGNAL",
                signal_source="inventory_fmv",
                asset_type="marketplace_listing",
                asset_id=201,
                signal_value=12.0,
                confidence_score=0.75,
                observed_at=now - timedelta(days=2),
                created_at=now - timedelta(days=2),
            )
        )
        session.add(
            MarketSignal(
                owner_user_id=owner_id,
                signal_type="FMV_SIGNAL",
                signal_source="inventory_fmv",
                asset_type="marketplace_listing",
                asset_id=201,
                signal_value=25.0,
                confidence_score=0.8,
                observed_at=now,
                created_at=now,
            )
        )
        session.add(
            MarketTrend(
                owner_user_id=owner_id,
                trend_type="ASSET_SIGNAL_VALUE",
                asset_type="marketplace_listing",
                asset_id=201,
                trend_direction="DOWN",
                trend_strength=0.9,
                confidence_score=0.85,
                calculated_at=now,
                created_at=now,
            )
        )
        session.add(
            MarketTrend(
                owner_user_id=owner_id,
                trend_type="TREND_STRENGTH",
                asset_type="marketplace_listing",
                asset_id=201,
                trend_direction="UP",
                trend_strength=0.6,
                confidence_score=0.7,
                calculated_at=now,
                created_at=now,
            )
        )
        session.add(
            MarketSnapshot(
                owner_user_id=owner_id,
                snapshot_date=now.date(),
                market_score=42.0,
                bullish_signals=1,
                bearish_signals=4,
                neutral_signals=1,
                created_at=now,
            )
        )
        session.commit()

        result = run_market_risk_agent(session, owner_user_id=owner_id)
        risks = session.exec(select(MarketRiskAssessment).where(MarketRiskAssessment.owner_user_id == owner_id)).all()

        assert result.execution.status == "COMPLETED"
        assert result.created_count >= 3
        assert any(row.risk_type == "HIGH_VOLATILITY_RISK" for row in risks)
        assert any(row.risk_type == "RAPID_PRICE_DECLINE_RISK" for row in risks)
        assert any(row.risk_type == "WEAK_DEMAND_RISK" for row in risks)
        assert all("recommend" not in row.risk_type.lower() for row in risks)
