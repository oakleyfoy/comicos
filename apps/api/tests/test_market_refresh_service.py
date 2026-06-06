from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.models.p70_market_refresh import P70MarketRefreshRun
from app.services.market_refresh_service import (
    list_refresh_runs,
    run_market_refresh_for_owner,
    select_refresh_target_copy_ids,
)
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_select_refresh_targets_includes_inventory(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "refresh-targets@example.com")
    owner_id = _owner_id(session, "refresh-targets@example.com")
    create_order(client, token)
    targets = select_refresh_target_copy_ids(session, owner_user_id=owner_id, limit=10)
    assert len(targets) >= 1


def test_run_market_refresh_persists_history(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "refresh-run@example.com")
    owner_id = _owner_id(session, "refresh-run@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    session.add(
        P68MarketPriceSnapshot(
            owner_user_id=owner_id,
            generated_at=datetime.now(timezone.utc),
            inventory_copy_id=int(copy.id or 0),
            title="Test",
            publisher="Marvel",
            issue_number="1",
            blended_fmv=25.0,
            sales_count=2,
            liquidity_score=40.0,
            confidence=0.6,
            metadata_json={"provider_breakdown": {"INTERNAL_SALE": 2}},
        )
    )
    session.commit()
    run = run_market_refresh_for_owner(session, owner_user_id=owner_id, trigger_type="MANUAL")
    session.commit()
    assert run.id is not None
    assert run.status in {"COMPLETED", "FAILED"}
    history = list_refresh_runs(session, owner_user_id=owner_id)
    assert len(history) >= 1
