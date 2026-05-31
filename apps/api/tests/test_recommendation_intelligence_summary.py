from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.recommendation_intelligence_summary import get_recommendation_intelligence_summary
from recommendation_intelligence_test_helpers import seed_recommendation_intelligence_certification_stack
from test_inventory import register_and_login


def test_recommendation_intelligence_summary(client: TestClient) -> None:
    email = "rec-intel-summary@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        summary = get_recommendation_intelligence_summary(session, owner_user_id=owner_id)
    assert summary.total_recommendations_v2 >= 1
    assert summary.v1_recommendation_count >= 1
    assert summary.explanation_count >= 1
    assert summary.readiness_score > 0
