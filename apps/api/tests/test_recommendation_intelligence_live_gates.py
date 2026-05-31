from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.recommendation_intelligence_live_gates import assess_live_p51_04_output
from recommendation_intelligence_test_helpers import seed_recommendation_intelligence_certification_stack
from test_inventory import register_and_login


def test_live_p51_04_gates_fail_without_run(client: TestClient) -> None:
    email = "live-gates-empty@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        assessment = assess_live_p51_04_output(session, owner_user_id=owner_id)
    assert assessment.live_output_ready is False
    assert assessment.blocking_reasons


def test_live_p51_04_gates_pass_after_seed_stack(client: TestClient) -> None:
    email = "live-gates-seeded@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        assessment = assess_live_p51_04_output(session, owner_user_id=owner_id)
    assert assessment.live_output_ready is True
    assert assessment.latest_issue_score_count >= 1
