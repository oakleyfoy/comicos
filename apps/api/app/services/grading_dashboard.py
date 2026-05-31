from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction, GradingRecommendation, GradingRoiAnalysis
from app.schemas.grading_intelligence import (
    GradePredictionRead,
    GradingAgentExecutionRead,
    GradingDashboardRead,
    GradingRecommendationRead,
    GradingRoiAnalysisRead,
)
from app.services.grading_intelligence import list_executions_for_owner


def _paginate_list(rows: list, limit: int, offset: int) -> tuple[list, int]:
    return rows[offset : offset + limit], len(rows)


def list_predictions_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradePrediction)
        .where(GradePrediction.owner_user_id == owner_user_id)
        .order_by(GradePrediction.created_at.desc(), GradePrediction.id.desc())
    ).all()
    page, total = _paginate_list(rows, limit, offset)
    return [GradePredictionRead.model_validate(row) for row in page], total


def list_recommendations_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradingRecommendation)
        .where(GradingRecommendation.owner_user_id == owner_user_id)
        .order_by(GradingRecommendation.created_at.desc(), GradingRecommendation.id.desc())
    ).all()
    page, total = _paginate_list(rows, limit, offset)
    return [GradingRecommendationRead.model_validate(row) for row in page], total


def list_roi_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradingRoiAnalysis)
        .where(GradingRoiAnalysis.owner_user_id == owner_user_id)
        .order_by(GradingRoiAnalysis.created_at.desc(), GradingRoiAnalysis.id.desc())
    ).all()
    page, total = _paginate_list(rows, limit, offset)
    return [GradingRoiAnalysisRead.model_validate(row) for row in page], total


def get_prediction_detail(session: Session, *, prediction_id: int, owner_user_id: int):
    from app.models.grading_intelligence import GradePredictionEvidence
    from app.schemas.grading_intelligence import GradePredictionDetail, GradePredictionEvidenceRead

    row = session.get(GradePrediction, prediction_id)
    if row is None or row.owner_user_id != owner_user_id:
        return None
    evidence = session.exec(
        select(GradePredictionEvidence).where(GradePredictionEvidence.prediction_id == prediction_id)
    ).all()
    return GradePredictionDetail(
        prediction=GradePredictionRead.model_validate(row),
        evidence=[GradePredictionEvidenceRead.model_validate(e) for e in evidence],
    )


def get_recommendation_detail(session: Session, *, recommendation_id: int, owner_user_id: int):
    from app.schemas.grading_intelligence import GradingRecommendationDetail
    from app.services.grading_review import list_reviews_for_recommendation

    row = session.get(GradingRecommendation, recommendation_id)
    if row is None or row.owner_user_id != owner_user_id:
        return None
    roi = session.exec(
        select(GradingRoiAnalysis)
        .where(GradingRoiAnalysis.recommendation_id == recommendation_id)
        .order_by(GradingRoiAnalysis.created_at.desc(), GradingRoiAnalysis.id.desc())
    ).first()
    return GradingRecommendationDetail(
        recommendation=GradingRecommendationRead.model_validate(row),
        reviews=list_reviews_for_recommendation(session, recommendation_id=recommendation_id),
        roi=GradingRoiAnalysisRead.model_validate(roi) if roi else None,
    )


def build_grading_dashboard(session: Session, *, owner_user_id: int) -> GradingDashboardRead:
    predictions, pred_count = list_predictions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    recommendations, rec_count = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    roi_rows, roi_count = list_roi_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    exec_rows, _ = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)

    from app.services.submission_priority_agent import rank_grading_candidates

    top = rank_grading_candidates(session, owner_user_id=owner_user_id)[:10]

    avg_conf = round(sum(p.confidence_score for p in predictions) / len(predictions), 3) if predictions else 0.0
    avg_pri = round(sum(r.priority_score for r in recommendations) / len(recommendations), 3) if recommendations else 0.0
    avg_roi = round(sum(r.expected_roi_percent for r in roi_rows) / len(roi_rows), 2) if roi_rows else 0.0

    return GradingDashboardRead(
        prediction_count=pred_count,
        recommendation_count=rec_count,
        roi_analysis_count=roi_count,
        average_confidence=avg_conf,
        average_priority=avg_pri,
        average_roi_percent=avg_roi,
        prediction_summary=predictions,
        recommendation_summary=recommendations,
        top_grading_candidates=top,
        roi_summary=roi_rows,
        agent_activity=[GradingAgentExecutionRead.model_validate(row) for row in exec_rows],
    )
