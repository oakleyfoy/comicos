from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.grade_prediction_agent import predict_grade
from app.services.grading_recommendation_agent import generate_grading_recommendations
from app.services.grading_intelligence_roi import run_roi_for_owner
from app.services.submission_priority_agent import calculate_submission_priority, rank_grading_candidates
from grading_test_helpers import seed_analysis_with_condition_pipeline
from test_inventory import register_and_login


def test_submission_priority_ranking(client: TestClient) -> None:
    email = "grade-priority@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        predict_grade(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        generate_grading_recommendations(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        run_roi_for_owner(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        ranked = rank_grading_candidates(session, owner_user_id=owner_user_id)
        assert ranked
        score = calculate_submission_priority(
            predicted_grade="9.4",
            confidence=0.8,
            roi_percent=20.0,
            recommendation_type="GRADE",
        )
        assert 0.0 <= score <= 1.0
