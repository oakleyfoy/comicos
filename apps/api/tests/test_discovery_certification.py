from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.discovery_certification import run_discovery_certification
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one


def test_discovery_certification_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-cert@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-cert@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    response = client.get("/api/v1/discovery/certification", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["approved_for_production"] is True
    assert body["failures"] == 0
    assert len(body["production_checklist"]) >= 6


def test_discovery_certification_service(client: TestClient, session: Session) -> None:
    register_and_login(client, "p81-cert-svc@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-cert-svc@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    cert = run_discovery_certification(session, owner_user_id=owner_id)
    assert cert.approved_for_production
    assert cert.checks_passed >= 10
    assert cert.platform_readiness_percent >= 90.0
