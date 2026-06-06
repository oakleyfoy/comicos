from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.platform_production_certification import run_platform_production_certification
from test_inventory import auth_headers, register_and_login


def test_platform_certification_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-cert@example.com")
    resp = client.get("/api/v1/platform/certification", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["certified_production_release"] is True
    assert body["status"] == "CERTIFIED_PRODUCTION_RELEASE"
    assert body["failures"] == 0
    assert len(body["categories"]) >= 15


def test_platform_certification_service(client: TestClient, session: Session) -> None:
    register_and_login(client, "p85-cert-svc@example.com")
    from sqlmodel import select
    from app.models import User

    owner_id = int(session.exec(select(User).where(User.email == "p85-cert-svc@example.com")).one().id or 0)
    cert = run_platform_production_certification(session, owner_user_id=owner_id)
    assert cert.certified_production_release
    assert cert.readiness_score >= 90.0
