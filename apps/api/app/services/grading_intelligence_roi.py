from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy
from app.models.grading_intelligence import GradePrediction, GradingRecommendation, GradingRoiAnalysis
from app.schemas.grading_intelligence import GradingRoiAnalysisRead
from app.services.grading_intelligence import AGENT_GRADING_ROI, run_with_grading_execution

DEFAULT_RAW_VALUE = 25.0
DEFAULT_GRADING_COST = 30.0

_GRADE_MULTIPLIERS: dict[str, float] = {
    "10": 3.5,
    "9.8": 2.8,
    "9.6": 2.2,
    "9.4": 1.9,
    "9.2": 1.6,
    "9.0": 1.4,
    "8.5": 1.2,
    "8.0": 1.05,
    "7.0": 0.95,
    "6.0": 0.85,
}


def calculate_raw_value(session: Session, *, inventory_copy_id: int | None, owner_user_id: int) -> float:
    if inventory_copy_id is None:
        return DEFAULT_RAW_VALUE
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        return DEFAULT_RAW_VALUE
    if copy.current_fmv is not None and copy.current_fmv > 0:
        return float(copy.current_fmv)
    if copy.acquisition_cost is not None and copy.acquisition_cost > 0:
        return float(copy.acquisition_cost)
    return DEFAULT_RAW_VALUE


def calculate_expected_graded_value(*, raw_value: float, predicted_grade: str) -> float:
    multiplier = _GRADE_MULTIPLIERS.get(predicted_grade, 1.1)
    return round(raw_value * multiplier, 2)


def calculate_grading_cost(*, grading_scale: str = "PSA") -> float:
    _ = grading_scale
    return DEFAULT_GRADING_COST


def calculate_expected_profit(*, expected_graded_value: float, raw_value: float, grading_cost: float) -> float:
    return round(expected_graded_value - raw_value - grading_cost, 2)


def calculate_roi_percent(*, expected_profit: float, raw_value: float, grading_cost: float) -> float:
    basis = max(raw_value + grading_cost, 1.0)
    return round((expected_profit / basis) * 100.0, 2)


def build_roi_analysis(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: GradingRecommendation,
    prediction: GradePrediction | None,
) -> GradingRoiAnalysisRead:
    raw = calculate_raw_value(session, inventory_copy_id=recommendation.inventory_copy_id, owner_user_id=owner_user_id)
    predicted_grade = prediction.predicted_grade if prediction else "8.0"
    scale = prediction.grading_scale if prediction else "PSA"
    graded = calculate_expected_graded_value(raw_value=raw, predicted_grade=predicted_grade)
    cost = calculate_grading_cost(grading_scale=scale)
    profit = calculate_expected_profit(expected_graded_value=graded, raw_value=raw, grading_cost=cost)
    roi = calculate_roi_percent(expected_profit=profit, raw_value=raw, grading_cost=cost)

    row = GradingRoiAnalysis(
        owner_user_id=owner_user_id,
        recommendation_id=int(recommendation.id) if recommendation.id else None,
        inventory_copy_id=recommendation.inventory_copy_id,
        raw_value=raw,
        expected_graded_value=graded,
        grading_cost=cost,
        expected_profit=profit,
        expected_roi_percent=roi,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return GradingRoiAnalysisRead.model_validate(row)


def run_roi_for_owner(session: Session, *, owner_user_id: int, analysis_id: int | None = None) -> list[GradingRoiAnalysisRead]:
    query = select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)
    if analysis_id is not None:
        preds = session.exec(select(GradePrediction.id).where(GradePrediction.analysis_id == analysis_id)).all()
        pred_ids = [int(x) for x in preds if x is not None]
        if not pred_ids:
            return []
        query = query.where(GradingRecommendation.prediction_id.in_(pred_ids))
    recs = session.exec(query.order_by(GradingRecommendation.created_at.desc(), GradingRecommendation.id.desc())).all()
    results: list[GradingRoiAnalysisRead] = []
    for rec in recs[:50]:
        prediction = session.get(GradePrediction, rec.prediction_id) if rec.prediction_id else None
        results.append(build_roi_analysis(session, owner_user_id=owner_user_id, recommendation=rec, prediction=prediction))
    return results


def run_grading_roi_agent(session: Session, *, owner_user_id: int, analysis_id: int | None = None) -> list[GradingRoiAnalysisRead]:
    def _run() -> list[GradingRoiAnalysisRead]:
        return run_roi_for_owner(session, owner_user_id=owner_user_id, analysis_id=analysis_id)

    result, _ = run_with_grading_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_GRADING_ROI,
        analysis_id=analysis_id,
        runner=_run,
    )
    return result
