from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.collector_profile_certification import run_collector_profile_certification
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_collector_profile_certification_service(client: TestClient, session: Session) -> None:
    register_and_login(client, "p77-cert@example.com")
    owner_id = _owner_id(session, "p77-cert@example.com")
    cert = run_collector_profile_certification(session, owner_user_id=owner_id)
    assert cert.approved_for_production is True, cert.failure_messages
    assert cert.platform_status == "APPROVED_FOR_PRODUCTION"
    assert cert.failures == 0
    assert cert.checks_passed >= 15
    assert len(cert.production_checklist) >= 7


def test_collector_profile_certification_api(client: TestClient) -> None:
    token = register_and_login(client, "p77-cert-api@example.com")
    response = client.get("/api/v1/collector-profile/certification", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["approved_for_production"] is True
    assert body["platform_readiness_percent"] >= 90.0


def test_p77_production_review_doc_exists() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "P77_PRODUCTION_REVIEW.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "P77-01" in text
    assert "P77-03" in text
    assert "certification" in text.lower()
