from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction, GradingRecommendation, GradingRoiAnalysis
from app.schemas.grading_intelligence import GradingRecommendationRead
from app.services.grading_intelligence import AGENT_SUBMISSION_PRIORITY, run_with_grading_execution


def calculate_submission_priority(
    *,
    predicted_grade: str,
    confidence: float,
    roi_percent: float,
    recommendation_type: str,
) -> float:
    grade_val = float(predicted_grade) if predicted_grade.replace(".", "", 1).isdigit() else 8.0
    type_boost = {
        "GRADE": 0.15,
        "REVIEW_MANUALLY": 0.05,
        "PRESS_CLEAN_FIRST": 0.08,
        "DO_NOT_GRADE": -0.2,
        "RESCAN_NEEDED": -0.15,
    }.get(recommendation_type, 0.0)
    roi_component = max(-0.1, min(0.25, roi_percent / 200.0))
    score = (grade_val / 10.0) * 0.35 + confidence * 0.35 + roi_component + type_boost
    return round(max(0.0, min(1.0, score)), 3)


def rank_grading_candidates(
    session: Session,
    *,
    owner_user_id: int,
) -> list[GradingRecommendationRead]:
    recs = session.exec(
        select(GradingRecommendation)
        .where(GradingRecommendation.owner_user_id == owner_user_id)
        .order_by(GradingRecommendation.created_at.desc(), GradingRecommendation.id.desc())
    ).all()

    ranked: list[tuple[float, GradingRecommendation]] = []
    for rec in recs:
        prediction = session.get(GradePrediction, rec.prediction_id) if rec.prediction_id else None
        roi_row = session.exec(
            select(GradingRoiAnalysis)
            .where(GradingRoiAnalysis.recommendation_id == rec.id)
            .order_by(GradingRoiAnalysis.created_at.desc(), GradingRoiAnalysis.id.desc())
        ).first()
        roi_percent = float(roi_row.expected_roi_percent) if roi_row else 0.0
        predicted = prediction.predicted_grade if prediction else "8.0"
        priority = calculate_submission_priority(
            predicted_grade=predicted,
            confidence=float(rec.confidence_score),
            roi_percent=roi_percent,
            recommendation_type=rec.recommendation_type,
        )
        ranked.append((priority, rec))

    ranked.sort(key=lambda item: (-item[0], -int(item[1].id or 0)))
    return [GradingRecommendationRead.model_validate(row) for _, row in ranked[:25]]


def run_submission_priority_agent(session: Session, *, owner_user_id: int) -> list[GradingRecommendationRead]:
    def _run() -> list[GradingRecommendationRead]:
        return rank_grading_candidates(session, owner_user_id=owner_user_id)

    result, _ = run_with_grading_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_SUBMISSION_PRIORITY,
        analysis_id=None,
        runner=_run,
    )
    return result
