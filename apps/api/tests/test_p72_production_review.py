from __future__ import annotations

from pathlib import Path

from app.services.grading_intelligence_certification import run_grading_intelligence_certification
from test_inventory import register_and_login
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_certification_passes_for_new_owner(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-cert@example.com")
    owner_id = _owner_id(session, "p72-cert@example.com")
    cert = run_grading_intelligence_certification(session, owner_user_id=owner_id)
    assert cert.approved_for_production is True
    assert cert.platform_status == "APPROVED_FOR_PRODUCTION"
    assert all(c.passed for c in cert.checks)

    resp = client.get(
        "/api/v1/grading-intelligence/certification",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["approved_for_production"] is True


def test_production_review_doc_exists() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "P72_PRODUCTION_REVIEW.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "APPROVED_FOR_PRODUCTION" in text
    assert "P72-01" in text and "P72-03" in text
