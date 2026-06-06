from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.asset_ledger import InventoryCopy
from test_inventory import auth_headers, register_and_login
from test_p78_sell_workflow import _seed_sell_copy


def test_publish_and_sync_listings(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-sync@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-sync@example.com")).one().id or 0)
    copy_id = _seed_sell_copy(session, owner_user_id=owner_id, copies=2)
    draft = client.post(
        "/api/v1/listing-drafts",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "status": "READY", "suggested_sell_quantity": 1},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["data"]["id"]

    pub = client.post(f"/api/v1/listings/{draft_id}/publish", headers=auth_headers(token))
    assert pub.status_code == 200, pub.text
    body = pub.json()["data"]
    assert body["listing"]["sync_state"] == "ACTIVE"
    assert body["listing"]["external_listing_id"]
    assert body["listing"]["listing_url"]
    assert len(body["reserved_copy_ids"]) == 1

    sync = client.post("/api/v1/listings/sync", headers=auth_headers(token))
    assert sync.status_code == 200, sync.text
    sync_data = sync.json()["data"]
    assert sync_data["sales_recorded"] >= 1

    listings = client.get("/api/v1/listings", headers=auth_headers(token))
    assert listings.status_code == 200
    items = listings.json()["data"]["items"]
    assert any(i["sync_state"] == "SOLD" for i in items)


def test_inventory_reservation_on_publish(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-reserve@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-reserve@example.com")).one().id or 0)
    copy_id = _seed_sell_copy(session, owner_user_id=owner_id, copies=5)
    draft = client.post(
        "/api/v1/listing-drafts",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "status": "READY", "suggested_sell_quantity": 3},
    )
    assert draft.status_code == 201
    draft_id = draft.json()["data"]["id"]

    pub = client.post(f"/api/v1/listings/{draft_id}/publish", headers=auth_headers(token))
    assert pub.status_code == 200
    assert len(pub.json()["data"]["reserved_copy_ids"]) == 3

    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all()
    listed = sum(1 for c in copies if (c.hold_status or "") == "listed")
    available = sum(1 for c in copies if (c.hold_status or "") == "hold")
    assert listed == 3
    assert available == 2
