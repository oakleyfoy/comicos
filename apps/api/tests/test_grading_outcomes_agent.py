from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction
from app.models.grading_validation import GradePredictionOutcome
from app.services.grade_prediction_agent import predict_grade
from app.services.grading_outcomes_agent import run_outcome_tracking
from app.services.grading_recommendation_agent import run_grading_recommendation_agent
from grading_test_helpers import seed_analysis_with_condition_pipeline


def test_grading_outcomes_agent_tracks_without_mutation(client) -> None:
    from app.db.session import get_engine
    from app.models import User
    from test_inventory import register_and_login

    email = "grade-out@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
        analysis_id = int(analysis.id)
        detail = predict_grade(session, owner_user_id=owner_user_id, analysis_id=analysis_id)
        prediction_id = detail.prediction.id
        predicted_grade = detail.prediction.predicted_grade
        run_grading_recommendation_agent(session, owner_user_id=owner_user_id, analysis_id=analysis_id)

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        outcomes, execution = run_outcome_tracking(session, owner_user_id=owner_user_id)
        assert execution.status == "COMPLETED"
        assert len(outcomes) >= 0
        pred_after = session.get(GradePrediction, prediction_id)
        assert pred_after is not None
        assert pred_after.predicted_grade == predicted_grade
        assert len(session.exec(select(GradePredictionOutcome)).all()) >= len(outcomes)
