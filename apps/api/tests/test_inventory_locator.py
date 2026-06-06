from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.inventory_locator_service import locate_inventory
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_locator_assigned_and_unassigned(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-loc2@example.com")
    owner_id = _owner_id(session, "p79-loc2@example.com")
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
                "quantity": 2,
                "raw_item_price": 4.99,
            }
        ],
    )
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all()
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    client.post(
        "/api/v1/storage/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"inventory_copy_id": int(copies[0].id or 0), "box_id": box_id, "slot_number": 53},
    )

    assigned = locate_inventory(session, owner_user_id=owner_id, query="Absolute")
    assert assigned.total_items >= 2
    hit = next(i for i in assigned.items if i.inventory_copy_id == int(copies[0].id or 0))
    assert hit.assignment_status == "ASSIGNED"
    assert hit.path.slot == 53
    assert hit.path.box == "17"

    unassigned_hit = next(
        (i for i in assigned.items if i.inventory_copy_id == int(copies[1].id or 0)),
        None,
    )
    assert unassigned_hit is not None
    assert unassigned_hit.assignment_status == "UNASSIGNED"

    resp = client.get(
        "/api/v1/storage/locator?q=Absolute",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["total_items"] >= 2
