from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_engine
from app.models import User
from app.services.personalization_agent import build_owner_preference_profile, generate_personalized_scores
from app.services.spec_scoring_agent import run_spec_scoring
from spec_test_helpers import seed_spec_release_inputs
from sqlmodel import Session


def test_personalization_weights_follow_runs_watchlists_and_orders(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="personalization@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)

        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)

        profile = build_owner_preference_profile(session, owner_user_id=owner_user_id)
        assert profile["purchase_history_count"] == 1

        personalized = generate_personalized_scores(session, owner_user_id=owner_user_id)
        assert personalized
        top = personalized[0]
        assert float(top["adjusted_score"]) >= float(top["base_score"])
        assert top["matched_preferences"]
