from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.models import User
from app.services.spec_scoring_agent import list_scores_for_owner, run_spec_scoring
from spec_test_helpers import seed_spec_release_inputs


def test_run_spec_scoring_generates_deterministic_scores(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="spec-scoring@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)

        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        created, execution = run_spec_scoring(session, owner_user_id=owner_user_id)
        assert execution.agent_code == "spec_scoring"
        assert execution.status == "COMPLETED"
        assert len(created) == 3
        assert {row.score_grade for row in created} >= {"BUY", "PASS"}

        second_run, second_execution = run_spec_scoring(session, owner_user_id=owner_user_id)
        assert second_execution.status == "COMPLETED"
        assert second_run == []

        listed, total = list_scores_for_owner(session, owner_user_id=owner_user_id, limit=10, offset=0)
        assert total == 3
        assert len(listed) == 3
