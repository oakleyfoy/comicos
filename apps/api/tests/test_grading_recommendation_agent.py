from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.grade_prediction_agent import predict_grade
from app.services.grading_recommendation_agent import generate_grading_recommendations
from grading_test_helpers import seed_analysis_with_condition_pipeline
from test_inventory import register_and_login


def test_grading_recommendation_agent(client: TestClient) -> None:
    email = "grade-rec@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        predict_grade(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        recs = generate_grading_recommendations(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        assert recs
        assert recs[0].recommendation_type in {
            "GRADE",
            "DO_NOT_GRADE",
            "REVIEW_MANUALLY",
            "RESCAN_NEEDED",
            "PRESS_CLEAN_FIRST",
        }
