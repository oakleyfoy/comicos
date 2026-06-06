from __future__ import annotations

from pathlib import Path

from app.services.recommendation_feedback_certification import run_recommendation_feedback_certification
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_inventory import register_and_login

from app.models import User


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_p73_certification_passes(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p73-cert@example.com")
    owner_id = _owner_id(session, "p73-cert@example.com")
    cert = run_recommendation_feedback_certification(session, owner_user_id=owner_id)
    assert cert.approved_for_production is True
    assert cert.platform_status == "APPROVED_FOR_PRODUCTION"
    assert all(c.passed for c in cert.checks)

    resp = client.get(
        "/api/v1/recommendation-feedback/certification",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["approved_for_production"] is True


def test_p73_production_review_doc_exists() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "P73_PRODUCTION_REVIEW.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "APPROVED_FOR_PRODUCTION" in text
    assert "P73-01" in text and "P73-03" in text
