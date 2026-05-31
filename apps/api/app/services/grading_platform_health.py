from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models.condition_intelligence import ConditionAgentExecution, ConditionProfile, ScanAnalysis
from app.models.grading_intelligence import (
    GradePrediction,
    GradingAgentExecution,
    GradingRecommendation,
    GradingRoiAnalysis,
)
from app.models.grading_validation import (
    GradeCalibrationMetric,
    GradeValidation,
    GradingReliabilityMetric,
    GradingValidationExecution,
)
from app.schemas.grading_platform import GradingPlatformHealthComponentRead, GradingPlatformHealthRead

HEALTH_STATUS_HEALTHY = "HEALTHY"
HEALTH_STATUS_WARNING = "WARNING"
HEALTH_STATUS_FAILED = "FAILED"
HEALTH_STATUS_DISABLED = "DISABLED"


def _aggregate_health(statuses: list[str]) -> str:
    if any(status == HEALTH_STATUS_FAILED for status in statuses):
        return HEALTH_STATUS_FAILED
    if any(status == HEALTH_STATUS_WARNING for status in statuses):
        return HEALTH_STATUS_WARNING
    if statuses and all(status == HEALTH_STATUS_DISABLED for status in statuses):
        return HEALTH_STATUS_DISABLED
    return HEALTH_STATUS_HEALTHY


def _component(
    *,
    component_code: str,
    title: str,
    health_status: str,
    summary: str,
    details_json: dict[str, object] | None = None,
) -> GradingPlatformHealthComponentRead:
    return GradingPlatformHealthComponentRead(
        component_code=component_code,
        title=title,
        health_status=health_status,
        summary=summary,
        details_json=details_json or {},
    )


def _execution_health(statuses: list[str]) -> str:
    if not statuses:
        return HEALTH_STATUS_WARNING
    if all(status == "FAILED" for status in statuses):
        return HEALTH_STATUS_FAILED
    if any(status == "FAILED" for status in statuses):
        return HEALTH_STATUS_WARNING
    if any(status == "RUNNING" for status in statuses):
        return HEALTH_STATUS_WARNING
    return HEALTH_STATUS_HEALTHY


def get_condition_intelligence_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthComponentRead:
    analyses = session.exec(select(ScanAnalysis).where(ScanAnalysis.owner_user_id == owner_user_id)).all()
    analysis_ids = [int(row.id or 0) for row in analyses]
    profiles = (
        session.exec(select(ConditionProfile).where(ConditionProfile.analysis_id.in_(analysis_ids))).all()
        if analysis_ids
        else []
    )
    executions = (
        session.exec(select(ConditionAgentExecution).where(ConditionAgentExecution.analysis_id.in_(analysis_ids))).all()
        if analysis_ids
        else []
    )
    status = _execution_health([row.status for row in executions])
    if not analyses and not profiles:
        status = HEALTH_STATUS_DISABLED
    elif not profiles:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="condition_intelligence_health",
        title="Condition Intelligence Health",
        health_status=status,
        summary=f"{len(analyses)} analyses, {len(profiles)} profiles, {len(executions)} agent executions.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_prediction_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthComponentRead:
    predictions = session.exec(select(GradePrediction).where(GradePrediction.owner_user_id == owner_user_id)).all()
    executions = session.exec(
        select(GradingAgentExecution)
        .where(GradingAgentExecution.owner_user_id == owner_user_id)
        .where(GradingAgentExecution.agent_code == "grade_prediction")
    ).all()
    status = _execution_health([row.status for row in executions])
    if not predictions:
        status = HEALTH_STATUS_WARNING if executions else HEALTH_STATUS_DISABLED
    return _component(
        component_code="prediction_health",
        title="Prediction Health",
        health_status=status,
        summary=f"{len(predictions)} predictions and {len(executions)} prediction agent executions.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_recommendation_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthComponentRead:
    recommendations = session.exec(
        select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)
    ).all()
    executions = session.exec(
        select(GradingAgentExecution)
        .where(GradingAgentExecution.owner_user_id == owner_user_id)
        .where(GradingAgentExecution.agent_code == "grading_recommendation")
    ).all()
    status = _execution_health([row.status for row in executions])
    if not recommendations:
        status = HEALTH_STATUS_WARNING if executions else HEALTH_STATUS_DISABLED
    return _component(
        component_code="recommendation_health",
        title="Recommendation Health",
        health_status=status,
        summary=f"{len(recommendations)} recommendations and {len(executions)} recommendation agent executions.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_roi_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthComponentRead:
    roi_rows = session.exec(select(GradingRoiAnalysis).where(GradingRoiAnalysis.owner_user_id == owner_user_id)).all()
    executions = session.exec(
        select(GradingAgentExecution)
        .where(GradingAgentExecution.owner_user_id == owner_user_id)
        .where(GradingAgentExecution.agent_code == "grading_roi")
    ).all()
    status = _execution_health([row.status for row in executions])
    if not roi_rows:
        status = HEALTH_STATUS_WARNING if executions else HEALTH_STATUS_DISABLED
    return _component(
        component_code="roi_health",
        title="ROI Health",
        health_status=status,
        summary=f"{len(roi_rows)} ROI analyses and {len(executions)} ROI agent executions.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_validation_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthComponentRead:
    validations = session.exec(select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)).all()
    executions = session.exec(
        select(GradingValidationExecution)
        .where(GradingValidationExecution.owner_user_id == owner_user_id)
        .where(GradingValidationExecution.agent_code == "grade_validation")
    ).all()
    status = _execution_health([row.status for row in executions])
    if not validations:
        status = HEALTH_STATUS_WARNING if executions else HEALTH_STATUS_DISABLED
    return _component(
        component_code="validation_health",
        title="Validation Health",
        health_status=status,
        summary=f"{len(validations)} validation records and {len(executions)} validation agent executions.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_calibration_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthComponentRead:
    metrics = session.exec(
        select(GradeCalibrationMetric).where(GradeCalibrationMetric.owner_user_id == owner_user_id)
    ).all()
    executions = session.exec(
        select(GradingValidationExecution)
        .where(GradingValidationExecution.owner_user_id == owner_user_id)
        .where(GradingValidationExecution.agent_code == "grading_calibration")
    ).all()
    status = _execution_health([row.status for row in executions])
    if not metrics:
        status = HEALTH_STATUS_WARNING if executions else HEALTH_STATUS_DISABLED
    elif metrics and any(float(row.accuracy_score) < 0.0 or float(row.accuracy_score) > 1.0 for row in metrics):
        status = HEALTH_STATUS_FAILED
    return _component(
        component_code="calibration_health",
        title="Calibration Health",
        health_status=status,
        summary=f"{len(metrics)} calibration metrics and {len(executions)} calibration agent executions.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_grading_platform_health(session: Session, *, owner_user_id: int) -> GradingPlatformHealthRead:
    components = [
        get_condition_intelligence_health(session, owner_user_id=owner_user_id),
        get_prediction_health(session, owner_user_id=owner_user_id),
        get_recommendation_health(session, owner_user_id=owner_user_id),
        get_roi_health(session, owner_user_id=owner_user_id),
        get_validation_health(session, owner_user_id=owner_user_id),
        get_calibration_health(session, owner_user_id=owner_user_id),
    ]
    return GradingPlatformHealthRead(
        overall_status=_aggregate_health([component.health_status for component in components]),
        components=components,
    )
