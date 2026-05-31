from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.models import User
from app.services.future_buy_queue import build_future_buy_queue
from app.services.spec_recommendation_agent import run_spec_recommendations
from app.services.spec_scoring_agent import run_spec_scoring
from release_platform_test_helpers import seed_release_platform_horizons


def test_future_buy_queue_generation(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="future-queue@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)
        run_spec_recommendations(session, owner_user_id=owner_user_id)

        queue = build_future_buy_queue(session, owner_user_id=owner_user_id)
        assert queue.next_90_days
        categories = {row.buy_category for row in queue.next_90_days}
        assert categories <= {"MUST_BUY", "STRONG_BUY", "WATCH", "PASS"}
