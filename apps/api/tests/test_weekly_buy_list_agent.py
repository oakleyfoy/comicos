from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import get_engine
from app.models import User
from app.services.spec_recommendation_agent import run_spec_recommendations
from app.services.spec_scoring_agent import run_spec_scoring
from app.services.weekly_buy_list_agent import list_weekly_buy_lists_for_owner, run_weekly_buy_list
from spec_test_helpers import seed_spec_release_inputs
from sqlmodel import Session


def test_weekly_buy_list_is_ranked_and_owner_scoped(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="weekly-buy-list@example.com", password_hash="x", is_active=True)
        outsider = User(email="weekly-buy-list-outsider@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.add(outsider)
        session.commit()
        session.refresh(owner)
        session.refresh(outsider)
        owner_user_id = int(owner.id or 0)
        outsider_user_id = int(outsider.id or 0)

        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)
        run_spec_recommendations(session, owner_user_id=owner_user_id)

        detail, execution = run_weekly_buy_list(session, owner_user_id=owner_user_id)
        assert execution.agent_code == "weekly_buy_list"
        assert detail.items
        assert detail.items[0].ranking_score >= detail.items[-1].ranking_score
        assert {row.buy_category for row in detail.items} >= {"Must Buy", "Strong Buy", "Pass"}

        owner_lists, owner_total = list_weekly_buy_lists_for_owner(
            session, owner_user_id=owner_user_id, limit=10, offset=0
        )
        outsider_lists, outsider_total = list_weekly_buy_lists_for_owner(
            session, owner_user_id=outsider_user_id, limit=10, offset=0
        )
        assert owner_total == 1
        assert len(owner_lists) == 1
        assert outsider_total == 0
        assert outsider_lists == []
