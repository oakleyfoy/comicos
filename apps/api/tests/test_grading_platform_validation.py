from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.grading_intelligence import GradePrediction, GradingRecommendation
from app.services.grading_platform_validation import validate_grading_platform
from grading_test_helpers import seed_full_grading_platform_stack
from test_inventory import register_and_login


def test_grading_platform_validation_returns_pass_without_mutation(client: TestClient) -> None:
    email = "grading-platform-validation@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_full_grading_platform_stack(session, owner_user_id=owner_id)
        prediction_count = len(session.exec(select(GradePrediction).where(GradePrediction.owner_user_id == owner_id)).all())
        recommendation_count = len(
            session.exec(select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_id)).all()
        )
        result = validate_grading_platform(session, owner_user_id=owner_id)
        assert result.overall_status == "PASS"
        assert result.platform_certified is True
        assert len(result.checks) == 5
        assert len(session.exec(select(GradePrediction).where(GradePrediction.owner_user_id == owner_id)).all()) == prediction_count
        assert (
            len(session.exec(select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_id)).all())
            == recommendation_count
        )
