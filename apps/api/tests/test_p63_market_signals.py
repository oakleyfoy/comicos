from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.market_signal_service import build_market_signals, list_market_signal_items
from app.services.portfolio_performance_service import build_portfolio_performance_snapshot
from app.services.p63_acquisition_opportunity_service import build_acquisition_opportunities
from app.services.sell_signal_service import build_sell_signals
from test_p63_market_helpers import seed_p63_owner
from test_inventory import register_and_login


def test_market_signals_with_explanations(client: TestClient, session: Session) -> None:
    email = "p63-sig@example.com"
    register_and_login(client, email)
    oid = seed_p63_owner(client, session, email)
    build_portfolio_performance_snapshot(session, owner_user_id=oid)
    build_sell_signals(session, owner_user_id=oid)
    build_acquisition_opportunities(session, owner_user_id=oid)
    snap = build_market_signals(session, owner_user_id=oid)
    items, total = list_market_signal_items(session, snapshot_id=int(snap.id or 0))
    assert total >= 1
    assert all(i.signal_reason for i in items)


def test_signals_api(client: TestClient, session: Session) -> None:
    email = "p63-sig-api@example.com"
    token = register_and_login(client, email)
    seed_p63_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/market-intelligence/platform/build", headers=headers)
    resp = client.get("/api/v1/market-intelligence/signals/latest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_items"] >= 1
