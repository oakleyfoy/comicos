from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.models.storage_location import P79StorageLocation
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_location_creation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-loc@example.com")
    owner_id = _owner_id(session, "p79-loc@example.com")
    build_office_rack_shelf_box(session, owner_user_id=owner_id)
    count = len(
        session.exec(select(P79StorageLocation).where(P79StorageLocation.owner_user_id == owner_id)).all()
    )
    assert count >= 4

    resp = client.get("/api/v1/storage/locations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) >= 4
    office = next(i for i in items if i["name"] == "Office")
    assert office["location_kind"] == "LOCATION"


def test_office_template_seed(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-seed@example.com")
    resp = client.post(
        "/api/v1/storage/locations",
        headers={"Authorization": f"Bearer {token}"},
        json={"location_kind": "LOCATION", "name": "ignored", "seed_office_template": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Office"
