from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.schemas.release_platform_certification import ReleasePlatformCertificationRead
from app.services.release_platform_health import HEALTH_STATUS_FAILED, get_release_platform_health
from app.services.release_platform_validation import PLATFORM_STATUS_PASS, validate_release_platform

CERTIFICATION_VERSION = "P50-05"
GO_LIVE_APPROVED = "APPROVED_FOR_PRODUCTION"
GO_LIVE_NOT_READY = "NOT_READY"


def get_release_platform_certification(session: Session, *, owner_user_id: int) -> ReleasePlatformCertificationRead:
    validation = validate_release_platform(session, owner_user_id=owner_user_id)
    health = get_release_platform_health(session, owner_user_id=owner_user_id)
    certified = validation.overall_status == PLATFORM_STATUS_PASS and health.overall_status != HEALTH_STATUS_FAILED

    notes: list[str] = []
    if validation.overall_status != PLATFORM_STATUS_PASS:
        notes.append("All release platform validation checks must pass for production certification.")
    if health.overall_status == HEALTH_STATUS_FAILED:
        notes.append("One or more release platform health components are currently failed.")
    if certified and not notes:
        notes.append(
            "Release Intelligence Platform (P50-01 through P50-04D) passed closeout validation for production use."
        )

    go_live = GO_LIVE_APPROVED if certified else GO_LIVE_NOT_READY
    return ReleasePlatformCertificationRead(
        platform_certified=certified,
        validation_status=validation.overall_status,
        health_status=health.overall_status,
        go_live_recommendation=go_live,
        certification_date=datetime.now(timezone.utc),
        certification_version=CERTIFICATION_VERSION,
        summary="Certified" if certified else "Not certified",
        certification_notes=notes,
    )
