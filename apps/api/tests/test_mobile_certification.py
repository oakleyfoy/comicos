from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.mobile_scanning_certification import run_mobile_scanning_certification
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_mobile_scanning_certification_service(client: TestClient, session: Session) -> None:
    register_and_login(client, "p80-cert@example.com")
    owner_id = _owner_id(session, "p80-cert@example.com")
    cert = run_mobile_scanning_certification(session, owner_user_id=owner_id)
    session.commit()
    cert2 = run_mobile_scanning_certification(session, owner_user_id=owner_id)
    session.commit()
    assert cert2.approved_for_production is True, cert2.failure_messages
    assert cert.approved_for_production is True
    assert cert.platform_status == "APPROVED_FOR_PRODUCTION"
    assert cert.failures == 0
    assert cert.checks_passed >= 20
    assert any(c.category == "collector_assistant" for c in cert.checks)


def test_mobile_certification_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-cert-api@example.com")
    response = client.get("/api/v1/mobile/certification", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["platform_status"] == "APPROVED_FOR_PRODUCTION"
    assert body["approved_for_production"] is True

    dashboard = client.get("/api/v1/mobile/certification-dashboard", headers=auth_headers(token))
    assert dashboard.status_code == 200, dashboard.text
    dash = dashboard.json()["data"]
    assert dash["platform_status"] == "APPROVED_FOR_PRODUCTION"
    assert len(dash["production_checklist"]) >= 8


def test_p80_production_review_doc_exists() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "P80_PRODUCTION_REVIEW.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "APPROVED_FOR_PRODUCTION" in text
    assert "P80-01" in text and "P80-03" in text
