from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradingRecommendation, GradingRecommendationReview, GradingRoiAnalysis
from app.models.grading_validation import GradePredictionOutcome
from app.models.grading_validation import GradingValidationExecution
from app.schemas.grading_validation import GradePredictionOutcomeRead, GradingValidationExecutionRead
from app.services.grading_validation import AGENT_GRADING_OUTCOMES, run_with_validation_execution


def track_recommendation_outcomes(session: Session, *, owner_user_id: int) -> list[GradePredictionOutcome]:
    outcomes: list[GradePredictionOutcome] = []
    recommendations = session.exec(
        select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)
    ).all()
    for recommendation in recommendations:
        review = session.exec(
            select(GradingRecommendationReview)
            .where(GradingRecommendationReview.recommendation_id == recommendation.id)
            .order_by(GradingRecommendationReview.reviewed_at.desc(), GradingRecommendationReview.id.desc())
        ).first()
        if review is None:
            continue
        status_score = 1.0 if review.review_status == "ACCEPTED" else 0.5 if review.review_status == "REVIEWED" else 0.2
        row = GradePredictionOutcome(
            owner_user_id=owner_user_id,
            recommendation_id=recommendation.id,
            prediction_id=recommendation.prediction_id,
            outcome_type=f"RECOMMENDATION_{review.review_status}",
            outcome_score=round(status_score * recommendation.confidence_score, 3),
        )
        session.add(row)
        outcomes.append(row)
    session.commit()
    for row in outcomes:
        session.refresh(row)
    return outcomes


def track_prediction_outcomes(session: Session, *, owner_user_id: int) -> list[GradePredictionOutcome]:
    from app.models.grading_validation import GradeValidation

    outcomes: list[GradePredictionOutcome] = []
    validations = session.exec(
        select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)
    ).all()
    for validation in validations:
        accuracy = max(0.0, 1.0 - validation.variance / 2.0)
        row = GradePredictionOutcome(
            owner_user_id=owner_user_id,
            prediction_id=validation.prediction_id,
            recommendation_id=None,
            outcome_type="PREDICTION_VALIDATION",
            outcome_score=round(accuracy, 3),
        )
        session.add(row)
        outcomes.append(row)
    session.commit()
    for row in outcomes:
        session.refresh(row)
    return outcomes


def track_roi_accuracy(session: Session, *, owner_user_id: int) -> list[GradePredictionOutcome]:
    outcomes: list[GradePredictionOutcome] = []
    roi_rows = session.exec(
        select(GradingRoiAnalysis).where(GradingRoiAnalysis.owner_user_id == owner_user_id)
    ).all()
    for roi in roi_rows:
        normalized = max(0.0, min(1.0, roi.expected_roi_percent / 100.0))
        row = GradePredictionOutcome(
            owner_user_id=owner_user_id,
            recommendation_id=roi.recommendation_id,
            prediction_id=None,
            outcome_type="ROI_EXPECTATION",
            outcome_score=round(normalized, 3),
        )
        session.add(row)
        outcomes.append(row)
    session.commit()
    for row in outcomes:
        session.refresh(row)
    return outcomes


def track_recommendation_outcomes_read(session: Session, *, owner_user_id: int) -> list[GradePredictionOutcomeRead]:
    return [GradePredictionOutcomeRead.model_validate(o) for o in track_recommendation_outcomes(session, owner_user_id=owner_user_id)]


def run_outcome_tracking(
    session: Session, *, owner_user_id: int
) -> tuple[list[GradePredictionOutcomeRead], GradingValidationExecutionRead]:
    def runner():
        combined: list[GradePredictionOutcome] = []
        combined.extend(track_recommendation_outcomes(session, owner_user_id=owner_user_id))
        combined.extend(track_prediction_outcomes(session, owner_user_id=owner_user_id))
        combined.extend(track_roi_accuracy(session, owner_user_id=owner_user_id))
        return [GradePredictionOutcomeRead.model_validate(o) for o in combined]

    result, execution = run_with_validation_execution(
        session, owner_user_id=owner_user_id, agent_code=AGENT_GRADING_OUTCOMES, runner=runner
    )
    assert isinstance(execution, GradingValidationExecution)
    return result, GradingValidationExecutionRead.model_validate(execution)


def list_outcomes_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradePredictionOutcome)
        .where(GradePredictionOutcome.owner_user_id == owner_user_id)
        .order_by(GradePredictionOutcome.created_at.desc(), GradePredictionOutcome.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [GradePredictionOutcomeRead.model_validate(row) for row in page], len(rows)
