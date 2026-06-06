from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.storage_missing_detection import build_detection_summary
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_missing_and_unassigned_detection(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-miss@example.com")
    owner_id = _owner_id(session, "p79-miss@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 5.0,
            }
        ],
    )
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all()
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    client.post(
        "/api/v1/storage/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"inventory_copy_id": int(copies[0].id or 0), "box_id": box_id, "slot_number": 1},
    )

    summary = build_detection_summary(session, owner_user_id=owner_id)
    assert summary.unassigned_books >= 1
