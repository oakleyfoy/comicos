from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.storage_assignment_service import suggest_next_slot_number
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_assignment_manual_and_suggested(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-assign@example.com")
    owner_id = _owner_id(session, "p79-assign@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Absolute Batman",
                "publisher": "DC",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            }
        ],
    )
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)

    assert suggest_next_slot_number(session, box_id=box_id) == 1

    resp = client.post(
        "/api/v1/storage/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"inventory_copy_id": copy_id, "box_id": box_id, "slot_number": 53},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["slot_number"] == 53
    assert data["box_name"] == "17"
    assert any(p["name"] == "Office" for p in data["location_path"])
