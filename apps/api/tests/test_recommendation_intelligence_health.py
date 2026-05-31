from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.recommendation_intelligence_health import get_recommendation_intelligence_health
from recommendation_intelligence_test_helpers import seed_recommendation_intelligence_certification_stack
from test_inventory import register_and_login


def test_recommendation_intelligence_health(client: TestClient) -> None:
    email = "rec-intel-health@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        health = get_recommendation_intelligence_health(session, owner_user_id=owner_id)
    assert health.overall_status in {"HEALTHY", "WARNING"}
    codes = {c.component_code for c in health.components}
    assert "recommendation_v2_engine" in codes
