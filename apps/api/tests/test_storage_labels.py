from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.storage_label_service import build_storage_label
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_label_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-label@example.com")
    owner_id = _owner_id(session, "p79-label@example.com")
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)

    label = build_storage_label(session, owner_user_id=owner_id, entity_type="box", entity_id=box_id)
    assert label.label_code.startswith("P79-BOX-")
    assert label.qr_payload.startswith("comicos://p79/storage/box/")
    assert "17" in label.printable_title or "17" in label.storage_path

    resp = client.get(
        f"/api/v1/storage/labels/box/{box_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["qr_payload"]
