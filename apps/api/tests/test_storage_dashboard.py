from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.storage_assignment_service import assign_inventory_copy
from app.services.storage_dashboard_service import build_storage_dashboard
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_dashboard_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-dash@example.com")
    owner_id = _owner_id(session, "p79-dash@example.com")
    create_order(client, token)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    assign_inventory_copy(
        session,
        owner_user_id=owner_id,
        inventory_copy_id=copy_id,
        box_id=box_id,
        use_suggested_slot=True,
    )

    dash = build_storage_dashboard(session, owner_user_id=owner_id)
    assert dash.location_count >= 4
    assert dash.box_count >= 1
    assert dash.assigned_books == 1
    assert dash.unassigned_books >= 0
    assert dash.available_slots >= 0

    resp = client.get("/api/v1/storage/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["assigned_books"] == 1
    assert "box_utilization_pct" in body
