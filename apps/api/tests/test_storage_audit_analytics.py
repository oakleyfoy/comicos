from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.storage_analytics_service import build_audit_analytics_read
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_audit_analytics(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-aan@example.com")
    owner_id = _owner_id(session, "p79-aan@example.com")
    create_order(client, token)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    client.post(
        "/api/v1/storage/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"inventory_copy_id": copy_id, "box_id": box_id, "slot_number": 1},
    )
    audit = client.post(
        "/api/v1/storage/audits",
        headers={"Authorization": f"Bearer {token}"},
        json={"audit_name": "Analytics audit", "scope_box_id": box_id},
    )
    entry_id = audit.json()["data"]["entries"][0]["id"]
    client.post(
        f"/api/v1/storage/audits/{audit.json()['data']['session']['id']}/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"entry_id": entry_id},
    )
    read = build_audit_analytics_read(session, owner_user_id=owner_id)
    assert read.audits_started >= 1
    resp = client.get("/api/v1/storage/audit-analytics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
