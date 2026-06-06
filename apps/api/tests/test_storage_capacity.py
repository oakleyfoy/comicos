from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.storage_assignment_service import assign_inventory_copy
from app.services.storage_capacity import box_metrics
from app.models.storage_location import P79StorageBox
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_capacity_tracking(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-cap@example.com")
    owner_id = _owner_id(session, "p79-cap@example.com")
    create_order(client, token)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    assign_inventory_copy(
        session,
        owner_user_id=owner_id,
        inventory_copy_id=copy_id,
        box_id=box_id,
        slot_number=1,
    )
    box = session.get(P79StorageBox, box_id)
    assert box is not None
    m = box_metrics(session, box=box)
    assert m["current_occupancy"] == 1
    assert m["remaining_capacity"] == 99
    assert m["utilization_pct"] == 1.0

    resp = client.get("/api/v1/storage/boxes", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    item = next(i for i in resp.json()["data"]["items"] if i["id"] == box_id)
    assert item["current_occupancy"] == 1
    assert item["suggested_next_slot"] == 2
