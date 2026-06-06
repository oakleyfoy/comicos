from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.storage_analytics_service import build_utilization_rows
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_utilization_by_location(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-util@example.com")
    owner_id = _owner_id(session, "p79-util@example.com")
    build_office_rack_shelf_box(session, owner_user_id=owner_id)
    rows = build_utilization_rows(session, owner_user_id=owner_id)
    kinds = {r.group_kind for r in rows}
    assert "BOX" in kinds
    assert "RACK" in kinds or "SHELF" in kinds
    resp = client.get("/api/v1/storage/utilization", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()["data"]["items"]) >= 1
