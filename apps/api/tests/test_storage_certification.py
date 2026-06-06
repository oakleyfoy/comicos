from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.storage_intelligence_certification import run_storage_intelligence_certification
from fastapi.testclient import TestClient
from test_inventory import create_order, register_and_login
from test_storage_helpers import build_office_rack_shelf_box


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_storage_certification_passes(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p79-cert@example.com")
    owner_id = _owner_id(session, "p79-cert@example.com")
    create_order(client, token)
    box_id, _ = build_office_rack_shelf_box(session, owner_user_id=owner_id)
    copy_id = int(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one().id or 0)
    cert = run_storage_intelligence_certification(
        session,
        owner_user_id=owner_id,
        inventory_copy_id=copy_id,
        box_id=box_id,
    )
    assert cert.approved_for_production is True
    assert cert.platform_status == "APPROVED_FOR_PRODUCTION"
    assert all(c.passed for c in cert.checks)

    resp = client.get("/api/v1/storage/certification", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["approved_for_production"] is True


def test_p79_production_review_doc_exists() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "P79_PRODUCTION_REVIEW.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "APPROVED_FOR_PRODUCTION" in text
    assert "P79-01" in text and "P79-03" in text
