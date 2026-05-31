from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_validation import GradingDriftEvent, GradingReliabilityMetric
from app.services.grade_prediction_agent import predict_grade
from app.services.grade_validation_agent import validate_predictions
from app.services.grading_reliability_agent import run_reliability_monitoring
from grading_test_helpers import seed_analysis_with_condition_pipeline


def test_grading_reliability_agent_generates_metrics(client) -> None:
    from app.db.session import get_engine
    from app.models import User
    from test_inventory import register_and_login

    email = "grade-rel@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        detail = predict_grade(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        validate_predictions(
            session,
            owner_user_id=owner_user_id,
            actual_grades=[(detail.prediction.id, detail.prediction.predicted_grade)],
        )

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        drift, reliability, execution = run_reliability_monitoring(session, owner_user_id=owner_user_id)
        assert execution.status == "COMPLETED"
        assert len(reliability) >= 1
        assert any(m.reliability_type == "SYSTEM_RELIABILITY" for m in reliability)
        assert len(session.exec(select(GradingReliabilityMetric)).all()) >= 1
        _ = drift
        _ = session.exec(select(GradingDriftEvent)).all()
