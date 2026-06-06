from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, Order, User
from fastapi.testclient import TestClient
from test_inventory import auth_headers, create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_mobile_intake_order_receive_flow(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-intake@example.com")
    owner_id = _owner_id(session, "p80-intake@example.com")
    order = create_order(client, token)
    order_id = int(order["order_id"])
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)

    start = client.post(
        "/api/v1/mobile/intake/start",
        headers=auth_headers(token),
        json={"intake_mode": "ORDER", "order_id": order_id},
    )
    assert start.status_code == 201, start.text
    session_id = start.json()["data"]["session_id"]
    assert start.json()["data"]["expected_count"] >= 1

    scan = client.post(
        "/api/v1/mobile/intake/scan",
        headers=auth_headers(token),
        json={"session_id": session_id, "barcode": str(copy_id)},
    )
    assert scan.status_code == 200, scan.text
    assert scan.json()["data"]["scan_status"] == "RECEIVED"
    assert scan.json()["data"]["inventory_copy_id"] == copy_id

    complete = client.post(
        "/api/v1/mobile/intake/complete",
        headers=auth_headers(token),
        json={"session_id": session_id},
    )
    assert complete.status_code == 200
    assert complete.json()["data"]["status_label"] == "COMPLETE"

    copy = session.get(InventoryCopy, copy_id)
    assert copy is not None
    assert copy.order_status == "received"


def test_mobile_storage_suggest_and_assign(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-store@example.com")
    owner_id = _owner_id(session, "p80-store@example.com")
    create_order(client, token)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)

    suggest = client.post(
        "/api/v1/mobile/storage/suggest",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "box_id": box_id},
    )
    assert suggest.status_code == 200, suggest.text
    assert suggest.json()["data"]["recommended_box_id"] == box_id
    assert suggest.json()["data"]["suggested_slot_number"] == 1

    assign = client.post(
        "/api/v1/mobile/storage/assign",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "box_id": box_id, "use_suggested_slot": True},
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["data"]["slot_number"] == 1


def test_mobile_audit_scan_and_complete(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-audit@example.com")
    owner_id = _owner_id(session, "p80-audit@example.com")
    create_order(client, token)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    client.post(
        "/api/v1/mobile/storage/assign",
        headers=auth_headers(token),
        json={"inventory_copy_id": copy_id, "box_id": box_id, "slot_number": 1},
    )

    start = client.post(
        "/api/v1/mobile/audit/start",
        headers=auth_headers(token),
        json={"audit_name": "Mobile box audit", "scope_box_id": box_id},
    )
    assert start.status_code == 201, start.text
    audit_id = start.json()["data"]["audit_id"]

    scan = client.post(
        "/api/v1/mobile/audit/scan",
        headers=auth_headers(token),
        json={"audit_id": audit_id, "barcode": str(copy_id)},
    )
    assert scan.status_code == 200, scan.text
    assert scan.json()["data"]["outcome"] == "VERIFIED"

    done = client.post(
        "/api/v1/mobile/audit/complete",
        headers=auth_headers(token),
        json={"audit_id": audit_id},
    )
    assert done.status_code == 200
    assert done.json()["data"]["verified_count"] == 1

    dash = client.get("/api/v1/mobile/operations", headers=auth_headers(token))
    assert dash.status_code == 200
    assert "intake_pending_receipts" in dash.json()["data"]
