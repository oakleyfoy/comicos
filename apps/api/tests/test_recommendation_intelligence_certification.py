from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.recommendation_intelligence_certification import (
    CERTIFICATION_VERSION,
    GO_LIVE_NOT_READY,
    get_recommendation_intelligence_certification,
)
from recommendation_intelligence_test_helpers import seed_recommendation_intelligence_certification_stack
from test_inventory import auth_headers, register_and_login


def test_recommendation_intelligence_not_ready_without_live_v2(client: TestClient) -> None:
    email = "rec-intel-not-ready@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        cert = get_recommendation_intelligence_certification(session, owner_user_id=owner_id)
    assert cert.platform_certified is False
    assert cert.go_live_recommendation == GO_LIVE_NOT_READY
    assert cert.certification_status == GO_LIVE_NOT_READY


def test_recommendation_intelligence_certification(client: TestClient) -> None:
    email = "rec-intel-cert@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        cert = get_recommendation_intelligence_certification(session, owner_user_id=owner_id)
    assert cert.certification_version == CERTIFICATION_VERSION
    assert cert.platform_certified is True
    assert cert.go_live_recommendation in {"APPROVED_FOR_RECOMMENDATION_USE", "APPROVED_WITH_WARNINGS"}


def test_recommendation_intelligence_certification_api(client: TestClient) -> None:
    email = "rec-intel-cert-api@example.com"
    token = register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
    resp = client.get("/api/v1/recommendation-intelligence/certification", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["platform_certified"] is True
