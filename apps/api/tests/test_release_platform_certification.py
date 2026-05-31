from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.release_platform_certification import CERTIFICATION_VERSION, get_release_platform_certification
from release_platform_test_helpers import seed_release_platform_certification_stack
from test_inventory import auth_headers, register_and_login


def test_release_platform_certification_approves_when_validation_passes(client: TestClient) -> None:
    email = "release-platform-certification@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_certification_stack(session, owner_user_id=owner_id)
        certification = get_release_platform_certification(session, owner_user_id=owner_id)
        assert certification.platform_certified is True
        assert certification.validation_status == "PASS"
        assert certification.health_status != "FAILED"
        assert certification.go_live_recommendation == "APPROVED_FOR_PRODUCTION"
        assert certification.certification_version == CERTIFICATION_VERSION


def test_release_platform_certification_api(client: TestClient) -> None:
    email = "release-platform-cert-api@example.com"
    token = register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_certification_stack(session, owner_user_id=owner_id)

    response = client.get("/api/v1/release-platform/certification", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["platform_certified"] is True
    assert body["go_live_recommendation"] == "APPROVED_FOR_PRODUCTION"
