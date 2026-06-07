from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from test_inventory import auth_headers, register_and_login
from test_p78_sell_workflow import _seed_sell_copy


def _publish_and_sync(client: TestClient, token: str, copy_id: int, qty: int = 1) -> int:
    draft = client.post(
        "/api/v1/p78/listing-drafts",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "status": "READY", "suggested_sell_quantity": qty},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["data"]["id"]
    pub = client.post(f"/api/v1/listings/{draft_id}/publish", headers=auth_headers(token))
    assert pub.status_code == 200, pub.text
    listing_id = pub.json()["data"]["listing"]["id"]
    sync = client.post("/api/v1/listings/sync", headers=auth_headers(token))
    assert sync.status_code == 200
    return int(listing_id)


def test_sales_roi_and_p73_outcome(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-sales@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-sales@example.com")).one().id or 0)
    copy_id = _seed_sell_copy(session, owner_user_id=owner_id, copies=1)
    listing_id = _publish_and_sync(client, token, copy_id)

    sales = client.get("/api/v1/sales", headers=auth_headers(token))
    assert sales.status_code == 200
    items = sales.json()["data"]["items"]
    assert len(items) >= 1
    sale = items[0]
    assert sale["sale_price"] > 0
    assert sale["cost_basis"] > 0
    assert sale["profit"] is not None
    assert sale["roi_pct"] != 0
    assert sale["p73_outcome_id"] is not None

    detail = client.get(f"/api/v1/sales/{sale['id']}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["data"]["listing_id"] == listing_id
