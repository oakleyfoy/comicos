from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.operations_reliability import RecoveryRecommendation
from app.services.platform_health import check_platform_health
from app.services.recovery_recommendations import generate_recovery_recommendations, rank_recommendations
from app.services.reliability_monitor import run_reliability_monitor
from test_inventory import register_and_login


def test_generate_recovery_recommendations_are_advisory_only(client: TestClient) -> None:
    register_and_login(client, "recovery-rec-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "recovery-rec-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)
        check_platform_health(session, owner_user_id=owner_user_id)
        run_reliability_monitor(session, owner_user_id=owner_user_id)
        before_integrity = len(session.exec(select(RecoveryRecommendation)).all())
        recs = generate_recovery_recommendations(session, owner_user_id=owner_user_id)
        after_integrity = len(session.exec(select(RecoveryRecommendation)).all())

    assert len(recs) >= 1
    assert after_integrity > before_integrity
    ranked = rank_recommendations(recs)
    assert ranked[0].priority_score >= ranked[-1].priority_score
