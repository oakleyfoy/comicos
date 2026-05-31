from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.models import User
from app.services.opportunity_intelligence import build_opportunity_intelligence
from app.services.spec_recommendation_agent import run_spec_recommendations
from app.services.spec_scoring_agent import run_spec_scoring
from release_platform_test_helpers import seed_release_platform_horizons


def test_opportunity_intelligence_ranking(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="opportunity@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)
        run_spec_recommendations(session, owner_user_id=owner_user_id)

        body = build_opportunity_intelligence(session, owner_user_id=owner_user_id)
        assert body.top_spec_opportunities
        assert body.top_new_number_ones
        scores = [row.ranking_score for row in body.top_spec_opportunities]
        assert scores == sorted(scores, reverse=True)
        if body.top_new_opportunities:
            assert all(row.score_components for row in body.top_new_opportunities)
