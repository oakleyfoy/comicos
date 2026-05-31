from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction
from app.models.grading_validation import GradeCalibrationMetric, GradeValidation
from app.services.grade_prediction_agent import predict_grade
from app.services.grade_validation_agent import calculate_variance, validate_predictions
from grading_test_helpers import seed_analysis_with_condition_pipeline


def test_grade_validation_agent_creates_validation_and_calibration(client) -> None:
    from app.db.session import get_engine
    from app.models import User
    from test_inventory import register_and_login

    email = "grade-val-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        detail = predict_grade(session, owner_user_id=owner_user_id, analysis_id=int(analysis.id))
        prediction_id = detail.prediction.id
        predicted = detail.prediction.predicted_grade
        before_pred = session.get(GradePrediction, prediction_id)
        assert before_pred is not None

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        actual = "8.0" if predicted != "8.0" else "9.0"
        validations, calibration, execution = validate_predictions(
            session,
            owner_user_id=owner_user_id,
            actual_grades=[(prediction_id, actual)],
        )
        assert len(validations) == 1
        assert validations[0].variance == calculate_variance(predicted_grade=predicted, actual_grade=actual)
        assert calibration is not None
        assert execution.status == "COMPLETED"
        after_pred = session.get(GradePrediction, prediction_id)
        assert after_pred.predicted_grade == before_pred.predicted_grade
        assert len(session.exec(select(GradeValidation)).all()) >= 1
        assert len(session.exec(select(GradeCalibrationMetric)).all()) >= 1
