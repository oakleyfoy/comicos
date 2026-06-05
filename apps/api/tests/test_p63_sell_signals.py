from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.sell_signal_service import build_sell_signals, list_sell_signal_items, update_sell_signal_item_status
from test_p63_market_helpers import seed_p63_owner
from test_inventory import register_and_login


def test_sell_signals_scoring_order(client: TestClient, session: Session) -> None:
    email = "p63-sell@example.com"
    register_and_login(client, email)
    oid = seed_p63_owner(client, session, email)
    snap = build_sell_signals(session, owner_user_id=oid)
    items, _ = list_sell_signal_items(session, snapshot_id=int(snap.id or 0))
    assert len(items) >= 1
    if len(items) > 1:
        assert items[0].sell_score >= items[1].sell_score


def test_sell_status_patch_api(client: TestClient, session: Session) -> None:
    email = "p63-sell-api@example.com"
    token = register_and_login(client, email)
    oid = seed_p63_owner(client, session, email)
    snap = build_sell_signals(session, owner_user_id=oid)
    items, _ = list_sell_signal_items(session, snapshot_id=int(snap.id or 0))
    item_id = int(items[0].id or 0)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.patch(
        f"/api/v1/market-intelligence/sell-signals/item/{item_id}",
        json={"status": "REVIEWED"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "REVIEWED"
    updated = update_sell_signal_item_status(session, item_id=item_id, owner_user_id=oid, status="REVIEWED")
    assert updated.status == "REVIEWED"
