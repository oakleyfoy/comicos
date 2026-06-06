from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.selling_certification import run_selling_certification
from test_inventory import auth_headers, register_and_login


def test_selling_certification_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p78-cert-api@example.com")
    response = client.get("/api/v1/selling-certification", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["approved_for_production"] is True
    assert body["failures"] == 0
    assert len(body["production_checklist"]) >= 7


def test_selling_certification_service(client: TestClient, session: Session) -> None:
    register_and_login(client, "p78-cert-svc@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p78-cert-svc@example.com")).one().id or 0)
    cert = run_selling_certification(session, owner_user_id=owner_id)
    assert cert.approved_for_production
    assert cert.failures == 0
    assert cert.platform_readiness_percent >= 90.0
