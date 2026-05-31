from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_validation import GradeCalibrationMetric, GradeValidation
from app.services.grade_prediction_agent import predict_grade
from app.services.grade_validation_agent import validate_predictions
from app.services.grading_calibration_agent import calculate_calibration_metrics
from grading_test_helpers import seed_analysis_with_condition_pipeline


def test_grading_calibration_agent_generates_metrics(client) -> None:
    from app.db.session import get_engine
    from app.models import User
    from test_inventory import register_and_login

    email = "grade-cal@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        detail = predict_grade(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        validate_predictions(
            session,
            owner_user_id=owner_user_id,
            actual_grades=[(detail.prediction.id, "9.0")],
        )

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        before_count = len(session.exec(select(GradeCalibrationMetric)).all())
        metrics, execution = calculate_calibration_metrics(session, owner_user_id=owner_user_id)
        assert execution.status == "COMPLETED"
        assert len(metrics) >= 1
        assert len(session.exec(select(GradeCalibrationMetric)).all()) > before_count
        assert len(session.exec(select(GradeValidation)).all()) >= 1
