from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.models.p70_market_refresh import P70MarketFmvTrendPoint
from app.services.market_trend_history_service import list_trend_points_for_copy, record_trend_points_from_snapshots
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_trend_history_records_and_labels(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "trend@example.com")
    owner_id = _owner_id(session, "trend@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    cid = int(copy.id or 0)
    prior_day = date.today() - timedelta(days=10)
    session.add(
        P70MarketFmvTrendPoint(
            owner_user_id=owner_id,
            inventory_copy_id=cid,
            recorded_on=prior_day,
            blended_fmv=30.0,
            confidence=0.5,
            liquidity_score=20.0,
            sales_count=1,
        )
    )
    snap = P68MarketPriceSnapshot(
        owner_user_id=owner_id,
        generated_at=datetime.now(timezone.utc),
        inventory_copy_id=cid,
        title="T",
        publisher="M",
        issue_number="1",
        blended_fmv=36.0,
        sales_count=3,
        liquidity_score=40.0,
        confidence=0.6,
        metadata_json={"provider_breakdown": {"EBAY_SOLD": 3}},
    )
    session.add(snap)
    session.flush()
    created = record_trend_points_from_snapshots(session, owner_user_id=owner_id, snapshots=[snap])
    session.commit()
    assert created == 1
    points = list_trend_points_for_copy(session, owner_user_id=owner_id, inventory_copy_id=cid, limit=5)
    assert points[0].price_trend_7d in {"RISING", "STABLE", "FALLING"}
    assert points[0].provider_breakdown_json.get("EBAY_SOLD") == 3
