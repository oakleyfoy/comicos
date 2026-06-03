from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.models import SpecRecommendation, User
from app.models.recommendation_v2 import RecommendationScoreV2
from app.services.recommendation_v2_engine import generate_recommendations_v2
from release_platform_test_helpers import seed_release_platform_horizons
from test_inventory import register_and_login


def test_recommendation_v2_engine_append_only(client: TestClient, session: Session) -> None:
    email = "rec-v2-engine@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    seed_release_platform_horizons(session, owner_user_id=owner_id)
    v1_before = session.exec(select(func.count()).select_from(SpecRecommendation)).one()
    run1 = generate_recommendations_v2(session, owner_user_id=owner_id)
    count1 = session.exec(
        select(func.count()).select_from(RecommendationScoreV2).where(RecommendationScoreV2.owner_user_id == owner_id)
    ).one()
    run2 = generate_recommendations_v2(session, owner_user_id=owner_id)
    count2 = session.exec(
        select(func.count()).select_from(RecommendationScoreV2).where(RecommendationScoreV2.owner_user_id == owner_id)
    ).one()
    v1_after = session.exec(select(func.count()).select_from(SpecRecommendation)).one()
    assert run1.recommendations_created >= 1
    assert count2 > count1
    assert v1_after == v1_before


def test_recommendation_v2_logs_progress_after_load(client: TestClient, session: Session) -> None:
    email = "rec-v2-progress@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    seed_release_platform_horizons(session, owner_user_id=owner_id)
    messages: list[str] = []
    generate_recommendations_v2(
        session,
        owner_user_id=owner_id,
        progress_callback=messages.append,
    )
    joined = "\n".join(messages)
    assert "load_release_issues rows=" in joined
    assert "filter_forward_window done" in joined
    assert "preload_scoring_context done" in joined
    assert "score_loop start" in joined
    assert any("score_progress issues=" in line for line in messages)
