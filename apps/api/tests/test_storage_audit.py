from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.p79_storage_audit import AUDIT_COMPLETED, ENTRY_MISSING, ENTRY_VERIFIED
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_audit_lifecycle(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-audit@example.com")
    owner_id = _owner_id(session, "p79-audit@example.com")
    create_order(client, token)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    client.post(
        "/api/v1/storage/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"inventory_copy_id": copy_id, "box_id": box_id, "slot_number": 1},
    )

    create_resp = client.post(
        "/api/v1/storage/audits",
        headers={"Authorization": f"Bearer {token}"},
        json={"audit_name": "Box 17 check", "scope_box_id": box_id},
    )
    assert create_resp.status_code == 200
    audit_id = create_resp.json()["data"]["session"]["id"]
    entry_id = create_resp.json()["data"]["entries"][0]["id"]

    verify_resp = client.post(
        f"/api/v1/storage/audits/{audit_id}/verify",
        headers={"Authorization": f"Bearer {token}"},
        json={"entry_id": entry_id},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["data"]["session"]["verified_count"] == 1

    missing_resp = client.post(
        f"/api/v1/storage/audits/{audit_id}/missing",
        headers={"Authorization": f"Bearer {token}"},
        json={"entry_id": entry_id, "notes": "not on shelf"},
    )
    assert missing_resp.status_code == 200

    complete_resp = client.post(
        f"/api/v1/storage/audits/{audit_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["data"]["session"]["status"] == AUDIT_COMPLETED
