from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.portfolio_performance_service import build_portfolio_performance_snapshot, list_portfolio_items
from test_p63_market_helpers import seed_p63_owner
from test_inventory import register_and_login


def test_portfolio_snapshot_build_and_order(client: TestClient, session: Session) -> None:
    email = "p63-port@example.com"
    register_and_login(client, email)
    oid = seed_p63_owner(client, session, email)
    snap = build_portfolio_performance_snapshot(session, owner_user_id=oid)
    items, total = list_portfolio_items(session, snapshot_id=int(snap.id or 0))
    assert total >= 1
    assert snap.total_items == total
    assert float(snap.total_cost_basis) > 0


def test_portfolio_api_build(client: TestClient, session: Session) -> None:
    email = "p63-port-api@example.com"
    token = register_and_login(client, email)
    seed_p63_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/market-intelligence/portfolio/build", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_items"] >= 1
