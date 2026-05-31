from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.grading_platform_summary import get_grading_platform_certification, get_grading_platform_summary
from grading_test_helpers import seed_full_grading_platform_stack
from test_inventory import register_and_login


def test_grading_platform_summary_and_certification(client: TestClient) -> None:
    email = "grading-platform-summary@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_full_grading_platform_stack(session, owner_user_id=owner_id)
        summary = get_grading_platform_summary(session, owner_user_id=owner_id)
        certification = get_grading_platform_certification(session, owner_user_id=owner_id)
        assert summary.condition_summary.analysis_count >= 1
        assert summary.prediction_summary.prediction_count >= 1
        assert summary.recommendation_summary.recommendation_count >= 1
        assert summary.roi_summary.roi_analysis_count >= 1
        assert summary.calibration_summary.validation_count >= 1
        assert certification.platform_certified is True
        assert certification.go_live_recommendation == "APPROVED_FOR_PERSONAL_USE"
