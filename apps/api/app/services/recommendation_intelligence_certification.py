from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.schemas.recommendation_intelligence_certification import RecommendationIntelligenceCertificationRead
from app.services.recommendation_intelligence_health import (
    HEALTH_FAILED,
    HEALTH_HEALTHY,
    HEALTH_WARNING,
    get_recommendation_intelligence_health,
)
from app.services.recommendation_intelligence_live_gates import assess_live_p51_04_output
from app.services.recommendation_intelligence_summary import get_recommendation_intelligence_summary
from app.services.recommendation_intelligence_validation import (
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
    validate_recommendation_intelligence,
)
from app.services.recommendation_quality_calibration import (
    CALIBRATION_FAIL,
    CALIBRATION_PASS,
    CALIBRATION_WARNING,
    calibrate_recommendation_quality,
)

CERTIFICATION_VERSION = "P51-05"
GO_LIVE_APPROVED = "APPROVED_FOR_RECOMMENDATION_USE"
GO_LIVE_WARNINGS = "APPROVED_WITH_WARNINGS"
GO_LIVE_NOT_READY = "NOT_READY"


def get_recommendation_intelligence_certification(
    session: Session,
    *,
    owner_user_id: int,
) -> RecommendationIntelligenceCertificationRead:
    """
    Certification is data-driven from live P51-04 output and closeout checks.
    Deploying P51-05 code alone never grants approval — NOT_READY until gates pass.
    """
    validation = validate_recommendation_intelligence(session, owner_user_id=owner_user_id)
    health = get_recommendation_intelligence_health(session, owner_user_id=owner_user_id)
    calibration = calibrate_recommendation_quality(session, owner_user_id=owner_user_id)
    summary = get_recommendation_intelligence_summary(session, owner_user_id=owner_user_id)
    live = assess_live_p51_04_output(session, owner_user_id=owner_user_id)

    notes: list[str] = list(live.blocking_reasons)
    if validation.overall_status == STATUS_FAIL:
        notes.append("Recommendation intelligence validation failed one or more checks.")
    if health.overall_status == HEALTH_FAILED:
        notes.append("One or more recommendation intelligence health components failed.")
    if calibration.overall_status == CALIBRATION_FAIL:
        notes.append("Quality calibration detected scoring distribution problems.")
    if summary.v1_recommendation_count == 0:
        notes.append("V1 spec recommendations not found (expected preserved history).")

    hard_block = (
        not live.live_output_ready
        or validation.overall_status == STATUS_FAIL
        or health.overall_status == HEALTH_FAILED
        or calibration.overall_status == CALIBRATION_FAIL
        or summary.v1_recommendation_count == 0
    )

    if hard_block:
        return RecommendationIntelligenceCertificationRead(
            platform_certified=False,
            certification_status=GO_LIVE_NOT_READY,
            go_live_recommendation=GO_LIVE_NOT_READY,
            readiness_score=min(summary.readiness_score, 79.0),
            certification_date=datetime.now(timezone.utc),
            certification_version=CERTIFICATION_VERSION,
            validation_status=validation.overall_status,
            health_status=health.overall_status,
            calibration_status=calibration.overall_status,
            certification_notes=notes
            or ["NOT_READY: complete a successful P51-04 V2 run and re-run certification."],
        )

    has_warnings = (
        validation.overall_status == STATUS_WARNING
        or health.overall_status == HEALTH_WARNING
        or calibration.overall_status == CALIBRATION_WARNING
    )

    if (
        validation.overall_status == STATUS_PASS
        and calibration.overall_status == CALIBRATION_PASS
        and health.overall_status == HEALTH_HEALTHY
    ):
        go_live = GO_LIVE_APPROVED
        cert_status = GO_LIVE_APPROVED
        notes.append(
            "Recommendation Intelligence Platform (P51-01 through P51-04) certified for advisory use "
            f"({live.latest_issue_score_count} live issue-level V2 scores)."
        )
        platform_certified = True
    elif has_warnings:
        go_live = GO_LIVE_WARNINGS
        cert_status = GO_LIVE_WARNINGS
        notes.append("Certified with warnings — review validation, health, and calibration findings.")
        platform_certified = True
    else:
        go_live = GO_LIVE_NOT_READY
        cert_status = GO_LIVE_NOT_READY
        platform_certified = False
        notes.append("NOT_READY: closeout checks did not meet approval thresholds.")

    return RecommendationIntelligenceCertificationRead(
        platform_certified=platform_certified,
        certification_status=cert_status,
        go_live_recommendation=go_live,
        readiness_score=summary.readiness_score,
        certification_date=datetime.now(timezone.utc),
        certification_version=CERTIFICATION_VERSION,
        validation_status=validation.overall_status,
        health_status=health.overall_status,
        calibration_status=calibration.overall_status,
        certification_notes=notes,
    )
