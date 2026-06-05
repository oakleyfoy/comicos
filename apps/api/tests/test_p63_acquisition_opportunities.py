from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.p63_acquisition_opportunity_service import build_acquisition_opportunities, list_acquisition_items
from test_p63_market_helpers import seed_p63_owner
from test_inventory import register_and_login


def test_acquisition_build_from_want_and_horizon(client: TestClient, session: Session) -> None:
    email = "p63-acq@example.com"
    register_and_login(client, email)
    oid = seed_p63_owner(client, session, email)
    snap = build_acquisition_opportunities(session, owner_user_id=oid)
    items, total = list_acquisition_items(session, snapshot_id=int(snap.id or 0))
    assert total >= 1
    assert items[0].opportunity_score >= items[-1].opportunity_score


def test_acquisition_api(client: TestClient, session: Session) -> None:
    email = "p63-acq-api@example.com"
    token = register_and_login(client, email)
    seed_p63_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post("/api/v1/market-intelligence/acquisition/build", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["total_items"] >= 1
