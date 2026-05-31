from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.recommendation_intelligence_validation import validate_recommendation_intelligence
from recommendation_intelligence_test_helpers import seed_recommendation_intelligence_certification_stack
from test_inventory import auth_headers, register_and_login


def test_recommendation_intelligence_validation(client: TestClient) -> None:
    email = "rec-intel-validation@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        result = validate_recommendation_intelligence(session, owner_user_id=owner_id)
    assert result.overall_status in {"PASS", "WARNING"}
    assert any(c.check_code == "p51_04_recommendation_v2" for c in result.checks)


def test_recommendation_intelligence_validation_api(client: TestClient) -> None:
    email = "rec-intel-validation-api@example.com"
    token = register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
    resp = client.get("/api/v1/recommendation-intelligence/validation", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["overall_status"] in {"PASS", "WARNING"}
