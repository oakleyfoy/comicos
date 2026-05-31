from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from grading_test_helpers import seed_full_grading_platform_stack
from test_inventory import auth_headers, register_and_login


def test_grading_platform_api_routes_are_owner_scoped(client: TestClient) -> None:
    owner_email = "grading-platform-api@example.com"
    outsider_email = "grading-platform-outsider@example.com"
    owner_token = register_and_login(client, owner_email)
    outsider_token = register_and_login(client, outsider_email)

    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == owner_email)).one().id or 0)
        seed_full_grading_platform_stack(session, owner_user_id=owner_id)

    summary = client.get("/api/v1/grading-platform/summary", headers=auth_headers(owner_token))
    health = client.get("/api/v1/grading-platform/health", headers=auth_headers(owner_token))
    validation = client.get("/api/v1/grading-platform/validation", headers=auth_headers(owner_token))
    certification = client.get("/api/v1/grading-platform/certification", headers=auth_headers(owner_token))
    outsider = client.get("/api/v1/grading-platform/summary", headers=auth_headers(outsider_token))

    assert summary.status_code == 200, summary.text
    assert health.status_code == 200, health.text
    assert validation.status_code == 200, validation.text
    assert certification.status_code == 200, certification.text
    assert validation.json()["data"]["overall_status"] == "PASS"
    assert certification.json()["data"]["platform_certified"] is True
    assert outsider.json()["data"]["prediction_summary"]["prediction_count"] == 0
