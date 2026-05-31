from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import select
from sqlmodel import Session

from app.db.session import get_engine
from app.models import User
from app.models.spec_intelligence import SpecRecommendation
from app.services.spec_recommendation_agent import list_recommendations_for_owner, run_spec_recommendations
from app.services.spec_review import mark_accepted, mark_dismissed, mark_reviewed
from app.services.spec_scoring_agent import run_spec_scoring
from spec_test_helpers import seed_spec_release_inputs


def test_spec_recommendations_and_reviews_are_append_only(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="spec-recommendations@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)

        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)
        created, execution = run_spec_recommendations(session, owner_user_id=owner_user_id)

        assert execution.agent_code == "spec_recommendation"
        assert len(created) == 3
        assert {row.recommendation_type for row in created} >= {"STRONG_BUY", "BUY", "PASS"}

        recommendation_id = created[0].id
        reviewed = mark_reviewed(
            session, owner_user_id=owner_user_id, recommendation_id=recommendation_id, review_notes="Manual look"
        )
        accepted = mark_accepted(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
        dismissed = mark_dismissed(
            session, owner_user_id=owner_user_id, recommendation_id=recommendation_id, review_notes="Not this week"
        )

        assert reviewed.review.review_status == "REVIEWED"
        assert accepted.review.review_status == "ACCEPTED"
        assert dismissed.review.review_status == "DISMISSED"

        listed, total = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=10, offset=0)
        assert total == 3
        assert len(listed) == 3
        assert session.exec(select(SpecRecommendation)).all()
