from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import ConditionProfile, ScanAnalysis
from app.models.grading_intelligence import GradePrediction, GradingRecommendation, GradingRoiAnalysis
from app.models.grading_validation import GradeCalibrationMetric, GradeValidation, GradingReliabilityMetric
from app.schemas.grading_platform import GradingPlatformValidationCheckRead, GradingPlatformValidationRead

PLATFORM_STATUS_PASS = "PASS"
PLATFORM_STATUS_WARNING = "WARNING"
PLATFORM_STATUS_FAIL = "FAIL"


def _aggregate_status(statuses: list[str]) -> str:
    if any(status == PLATFORM_STATUS_FAIL for status in statuses):
        return PLATFORM_STATUS_FAIL
    if any(status == PLATFORM_STATUS_WARNING for status in statuses):
        return PLATFORM_STATUS_WARNING
    return PLATFORM_STATUS_PASS


def _check(
    *,
    check_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> GradingPlatformValidationCheckRead:
    return GradingPlatformValidationCheckRead(
        check_code=check_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def validate_condition_intelligence(session: Session, *, owner_user_id: int) -> GradingPlatformValidationCheckRead:
    analyses = session.exec(select(ScanAnalysis).where(ScanAnalysis.owner_user_id == owner_user_id)).all()
    analysis_ids = [int(row.id or 0) for row in analyses]
    profiles = (
        session.exec(select(ConditionProfile).where(ConditionProfile.analysis_id.in_(analysis_ids))).all()
        if analysis_ids
        else []
    )
    invalid_scores = [
        int(row.id or 0)
        for row in profiles
        if float(row.overall_condition_score) < 0.0 or float(row.overall_condition_score) > 100.0
    ]
    status = PLATFORM_STATUS_PASS
    if invalid_scores:
        status = PLATFORM_STATUS_FAIL
    elif not analyses or not profiles:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="condition_intelligence",
        title="Condition Intelligence",
        status=status,
        summary=f"{len(analyses)} analyses and {len(profiles)} condition profiles reviewed.",
        details_json={
            "owner_user_id": owner_user_id,
            "analysis_count": len(analyses),
            "profile_count": len(profiles),
            "invalid_profile_ids": invalid_scores,
        },
    )


def validate_grade_predictions(session: Session, *, owner_user_id: int) -> GradingPlatformValidationCheckRead:
    predictions = session.exec(select(GradePrediction).where(GradePrediction.owner_user_id == owner_user_id)).all()
    invalid_confidence = [
        int(row.id or 0)
        for row in predictions
        if float(row.confidence_score) < 0.0 or float(row.confidence_score) > 1.0
    ]
    status = PLATFORM_STATUS_PASS
    if invalid_confidence:
        status = PLATFORM_STATUS_FAIL
    elif not predictions:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="grade_predictions",
        title="Grade Predictions",
        status=status,
        summary=f"{len(predictions)} grade predictions validated for confidence bounds.",
        details_json={
            "owner_user_id": owner_user_id,
            "prediction_count": len(predictions),
            "invalid_confidence_prediction_ids": invalid_confidence,
        },
    )


def validate_grading_recommendations(session: Session, *, owner_user_id: int) -> GradingPlatformValidationCheckRead:
    recommendations = session.exec(
        select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)
    ).all()
    invalid = [
        int(row.id or 0)
        for row in recommendations
        if float(row.confidence_score) < 0.0
        or float(row.confidence_score) > 1.0
        or float(row.priority_score) < 0.0
    ]
    status = PLATFORM_STATUS_PASS
    if invalid:
        status = PLATFORM_STATUS_FAIL
    elif not recommendations:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="grading_recommendations",
        title="Grading Recommendations",
        status=status,
        summary=f"{len(recommendations)} advisory grading recommendations reviewed.",
        details_json={
            "owner_user_id": owner_user_id,
            "recommendation_count": len(recommendations),
            "invalid_recommendation_ids": invalid,
        },
    )


def validate_roi_analysis(session: Session, *, owner_user_id: int) -> GradingPlatformValidationCheckRead:
    roi_rows = session.exec(select(GradingRoiAnalysis).where(GradingRoiAnalysis.owner_user_id == owner_user_id)).all()
    invalid = [int(row.id or 0) for row in roi_rows if float(row.grading_cost) < 0.0]
    status = PLATFORM_STATUS_PASS
    if invalid:
        status = PLATFORM_STATUS_FAIL
    elif not roi_rows:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="roi_analysis",
        title="ROI Analysis",
        status=status,
        summary=f"{len(roi_rows)} grading ROI analyses checked.",
        details_json={
            "owner_user_id": owner_user_id,
            "roi_count": len(roi_rows),
            "invalid_roi_ids": invalid,
        },
    )


def validate_grading_validation(session: Session, *, owner_user_id: int) -> GradingPlatformValidationCheckRead:
    validations = session.exec(select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)).all()
    calibration = session.exec(
        select(GradeCalibrationMetric).where(GradeCalibrationMetric.owner_user_id == owner_user_id)
    ).all()
    reliability = session.exec(
        select(GradingReliabilityMetric).where(GradingReliabilityMetric.owner_user_id == owner_user_id)
    ).all()
    status = PLATFORM_STATUS_PASS
    if validations and any(float(row.variance) < 0.0 for row in validations):
        status = PLATFORM_STATUS_FAIL
    elif not validations or not calibration:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="grading_validation",
        title="Grading Validation",
        status=status,
        summary=(
            f"{len(validations)} validations, {len(calibration)} calibration metrics, "
            f"and {len(reliability)} reliability metrics reviewed."
        ),
        details_json={
            "owner_user_id": owner_user_id,
            "validation_count": len(validations),
            "calibration_metric_count": len(calibration),
            "reliability_metric_count": len(reliability),
        },
    )


def validate_grading_platform(session: Session, *, owner_user_id: int) -> GradingPlatformValidationRead:
    checks = [
        validate_condition_intelligence(session, owner_user_id=owner_user_id),
        validate_grade_predictions(session, owner_user_id=owner_user_id),
        validate_grading_recommendations(session, owner_user_id=owner_user_id),
        validate_roi_analysis(session, owner_user_id=owner_user_id),
        validate_grading_validation(session, owner_user_id=owner_user_id),
    ]
    overall = _aggregate_status([check.status for check in checks])
    return GradingPlatformValidationRead(
        overall_status=overall,
        platform_certified=overall == PLATFORM_STATUS_PASS,
        checks=checks,
    )
