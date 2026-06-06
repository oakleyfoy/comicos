from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.collector_expansion_certification import run_collector_expansion_certification
from test_inventory import auth_headers, register_and_login


def test_collector_expansion_certification_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p82-cert@example.com")
    resp = client.get("/api/v1/collector-expansion/certification", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["approved_for_production"] is True
    assert body["status"] == "APPROVED_FOR_PRODUCTION"
    assert body["failures"] == 0


def test_collector_expansion_certification_service(client: TestClient, session: Session) -> None:
    register_and_login(client, "p82-cert-svc@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p82-cert-svc@example.com")).one().id or 0)
    cert = run_collector_expansion_certification(session, owner_user_id=owner_id)
    failed = [c for c in cert.checks if not c.passed]
    assert cert.approved_for_production, failed
    assert cert.checks_passed >= 10
