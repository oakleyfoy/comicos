from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.grading_intelligence import GradePrediction, GradePredictionEvidence
from app.services.grade_prediction_agent import predict_grade, predict_grade_range
from grading_test_helpers import seed_analysis_with_condition_pipeline
from test_inventory import register_and_login


def test_grade_prediction_agent_generates_prediction_and_evidence(client: TestClient) -> None:
    email = "grade-pred@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        detail = predict_grade(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        assert detail.prediction.grading_scale == "PSA"
        assert detail.prediction.predicted_grade
        assert detail.prediction.grade_floor
        assert detail.prediction.grade_ceiling
        assert len(detail.evidence) >= 1
        floor, ceiling = predict_grade_range(
            predicted_grade=detail.prediction.predicted_grade,
            condition_score=90.0,
            defect_count=1,
        )
        assert float(floor) <= float(detail.prediction.predicted_grade) <= float(ceiling) + 1.0
        stored = session.exec(select(GradePrediction).where(GradePrediction.analysis_id == analysis.id)).all()
        assert len(stored) == 1
        evidence = session.exec(
            select(GradePredictionEvidence).where(GradePredictionEvidence.prediction_id == stored[0].id)
        ).all()
        assert len(evidence) >= 1
