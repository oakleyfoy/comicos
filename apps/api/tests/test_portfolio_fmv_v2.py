"""P90 portfolio FMV V2 tests."""

from __future__ import annotations

from sqlmodel import Session

from app.models.p90_fmv_snapshot import P90FmvSnapshot, utc_now
from app.services.portfolio_fmv_v2_service import build_portfolio_fmv_v2
from test_inventory import create_order, register_and_login


def test_portfolio_aggregation(client, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    token = register_and_login(client, "fmv-v2-port@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "fmv-v2-port@example.com")).one()
    session.add(
        P90FmvSnapshot(
            owner_user_id=int(user.id),
            series="Test",
            issue_number="1",
            variant="",
            quick_sale_value=30,
            market_value=40,
            premium_value=45,
            valuation_confidence="HIGH",
            trend_direction="UP",
            trend_score=12,
            sales_velocity="NORMAL",
            listing_count=3,
            marketplace_count=1,
            valuation_source="MARKETPLACE",
            snapshot_date=utc_now().date(),
            created_at=utc_now(),
        )
    )
    session.commit()
    portfolio = build_portfolio_fmv_v2(session, owner_user_id=int(user.id))
    assert portfolio["market_portfolio_value"] >= 0
    assert portfolio["confidence_high"] >= 0
