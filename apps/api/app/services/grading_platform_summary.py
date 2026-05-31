from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_validation import GradeCalibrationMetric, GradeValidation, GradingDriftEvent, GradingReliabilityMetric
from app.schemas.grading_intelligence import GradingRecommendationRead, GradingRoiAnalysisRead
from app.schemas.grading_platform import (
    GradingPlatformCalibrationSummary,
    GradingPlatformCertificationRead,
    GradingPlatformConditionSummary,
    GradingPlatformPredictionSummary,
    GradingPlatformRecommendationSummary,
    GradingPlatformReliabilitySummary,
    GradingPlatformRoiSummary,
    GradingPlatformSummaryRead,
)
from app.schemas.grading_validation import GradeCalibrationMetricRead, GradingReliabilityMetricRead
from app.services.condition_dashboard import build_condition_dashboard
from app.services.grading_dashboard import build_grading_dashboard
from app.services.grading_platform_health import get_grading_platform_health
from app.services.grading_platform_validation import validate_grading_platform
from app.services.submission_priority_agent import rank_grading_candidates


def get_grading_platform_summary(session: Session, *, owner_user_id: int) -> GradingPlatformSummaryRead:
    condition = build_condition_dashboard(session, owner_user_id=owner_user_id)
    grading = build_grading_dashboard(session, owner_user_id=owner_user_id)

    validations = session.exec(select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)).all()
    calibration_rows = session.exec(
        select(GradeCalibrationMetric).where(GradeCalibrationMetric.owner_user_id == owner_user_id)
    ).all()
    reliability_rows = session.exec(
        select(GradingReliabilityMetric).where(GradingReliabilityMetric.owner_user_id == owner_user_id)
    ).all()
    drift_count = len(
        session.exec(select(GradingDriftEvent).where(GradingDriftEvent.owner_user_id == owner_user_id)).all()
    )

    calibration_reads = [GradeCalibrationMetricRead.model_validate(row) for row in calibration_rows[:5]]
    reliability_reads = [GradingReliabilityMetricRead.model_validate(row) for row in reliability_rows[:5]]
    avg_accuracy = (
        round(sum(float(row.accuracy_score) for row in calibration_rows) / len(calibration_rows), 3)
        if calibration_rows
        else 0.0
    )
    avg_reliability = (
        round(sum(float(row.metric_score) for row in reliability_rows) / len(reliability_rows), 3)
        if reliability_rows
        else 0.0
    )

    top_candidates = [
        GradingRecommendationRead.model_validate(row)
        for row in rank_grading_candidates(session, owner_user_id=owner_user_id)[:5]
    ]

    return GradingPlatformSummaryRead(
        condition_summary=GradingPlatformConditionSummary(
            analysis_count=condition.analysis_count,
            profile_count=condition.profile_count,
            average_condition_score=condition.average_condition_score,
            average_quality_score=condition.average_quality_score,
        ),
        prediction_summary=GradingPlatformPredictionSummary(
            prediction_count=grading.prediction_count,
            average_confidence=grading.average_confidence,
            recent_predictions=grading.prediction_summary,
        ),
        recommendation_summary=GradingPlatformRecommendationSummary(
            recommendation_count=grading.recommendation_count,
            average_priority=grading.average_priority,
            recent_recommendations=grading.recommendation_summary,
        ),
        roi_summary=GradingPlatformRoiSummary(
            roi_analysis_count=grading.roi_analysis_count,
            average_roi_percent=grading.average_roi_percent,
            recent_roi=grading.roi_summary,
        ),
        calibration_summary=GradingPlatformCalibrationSummary(
            validation_count=len(validations),
            calibration_metric_count=len(calibration_rows),
            average_accuracy_score=avg_accuracy,
            recent_calibration=calibration_reads,
        ),
        reliability_summary=GradingPlatformReliabilitySummary(
            reliability_metric_count=len(reliability_rows),
            drift_event_count=drift_count,
            average_reliability_score=avg_reliability,
            recent_reliability=reliability_reads,
        ),
        top_grading_candidates=top_candidates,
    )


def get_grading_platform_certification(session: Session, *, owner_user_id: int) -> GradingPlatformCertificationRead:
    validation = validate_grading_platform(session, owner_user_id=owner_user_id)
    health = get_grading_platform_health(session, owner_user_id=owner_user_id)
    certified = validation.platform_certified and health.overall_status in {HEALTH_STATUS_HEALTHY, HEALTH_STATUS_WARNING}
    notes: list[str] = []
    if validation.overall_status != "PASS":
        notes.append("All grading platform validation checks must pass for full certification.")
    if health.overall_status == "FAILED":
        notes.append("One or more grading health components are currently failed.")
    if health.overall_status == "DISABLED":
        notes.append("Run condition and grading agents to populate platform activity before go-live.")
    go_live = "APPROVED_FOR_PERSONAL_USE" if certified else "NOT_READY"
    if certified and not notes:
        notes.append(
            "Grading Intelligence Platform (P49-01 through P49-03) passed closeout validation for personal production use."
        )
    return GradingPlatformCertificationRead(
        platform_certified=certified,
        validation_status=validation.overall_status,
        health_status=health.overall_status,
        summary="Certified" if certified else "Not certified",
        go_live_recommendation=go_live,
        certification_notes=notes,
    )


HEALTH_STATUS_HEALTHY = "HEALTHY"
HEALTH_STATUS_WARNING = "WARNING"
