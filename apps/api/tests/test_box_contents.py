from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.box_contents_service import get_box_contents
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_box_contents_sorted_and_grouped(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-boxc@example.com")
    owner_id = _owner_id(session, "p79-boxc@example.com")
    create_order(client, token)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    client.post(
        "/api/v1/storage/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"inventory_copy_id": copy_id, "box_id": box_id, "slot_number": 53},
    )

    contents = get_box_contents(session, owner_user_id=owner_id, box_id=box_id)
    assert contents.total_count == 1
    assert contents.sections
    assert contents.sections[0].section == "Section 3"
    assert contents.sections[0].items[0].slot_number == 53

    resp = client.get(
        f"/api/v1/storage/boxes/{box_id}/contents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["total_count"] == 1
