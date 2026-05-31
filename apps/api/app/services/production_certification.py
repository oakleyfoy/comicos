from __future__ import annotations

from sqlmodel import Session, select

from app.models.production_readiness import GoLiveAssessment, ProductionCertification, ProductionReadinessCheck
from app.schemas.production_readiness import (
    GoLiveAssessmentRead,
    ProductionCertificationRead,
    ProductionReadinessDashboardRead,
)
from app.services.production_readiness import CHECK_STATUS_FAIL, CHECK_STATUS_PASS, CHECK_STATUS_WARNING
from app.services.production_readiness_notes import encode_scoped_notes, notes_owner_user_id, notes_summary
from app.services.readiness_checklist import latest_checklist_summary_for_owner

STATUS_SCORES = {
    CHECK_STATUS_PASS: 100.0,
    CHECK_STATUS_WARNING: 70.0,
    CHECK_STATUS_FAIL: 0.0,
    "COMPLETE": 100.0,
    "INCOMPLETE": 40.0,
    "NOT_RUN": 30.0,
}


def calculate_readiness_score(check_statuses: list[str]) -> float:
    if not check_statuses:
        return 0.0
    scores = [STATUS_SCORES.get(status, 50.0) for status in check_statuses]
    return round(sum(scores) / len(scores), 1)


def _certification_status(score: float, statuses: list[str]) -> str:
    if any(status == CHECK_STATUS_FAIL for status in statuses):
        return "NOT_CERTIFIED"
    if score >= 85.0 and all(status == CHECK_STATUS_PASS for status in statuses):
        return "CERTIFIED"
    if score >= 60.0:
        return "CONDITIONAL"
    return "NOT_CERTIFIED"


def _go_live_status(certification_status: str, score: float) -> str:
    if certification_status == "CERTIFIED" and score >= 85.0:
        return "GO"
    if certification_status == "CONDITIONAL":
        return "CONDITIONAL"
    return "NO_GO"


def _to_certification_read(row: ProductionCertification) -> ProductionCertificationRead:
    data = row.model_dump()
    data["certification_notes"] = notes_summary(row.certification_notes)
    return ProductionCertificationRead.model_validate(data)


def _to_assessment_read(row: GoLiveAssessment) -> GoLiveAssessmentRead:
    data = row.model_dump()
    data["assessment_summary"] = notes_summary(row.assessment_summary)
    return GoLiveAssessmentRead.model_validate(data)


def generate_certification(
    session: Session,
    *,
    owner_user_id: int,
    check_statuses: list[str] | None = None,
) -> ProductionCertificationRead:
    if check_statuses is None:
        rows = session.exec(
            select(ProductionReadinessCheck).order_by(
                ProductionReadinessCheck.checked_at.desc(),
                ProductionReadinessCheck.id.desc(),
            )
        ).all()
        owner_rows = [row for row in rows if notes_owner_user_id(row.check_notes) == owner_user_id]
        latest_by_subsystem: dict[str, str] = {}
        for row in owner_rows:
            if row.subsystem not in latest_by_subsystem:
                latest_by_subsystem[row.subsystem] = row.check_status
        check_statuses = list(latest_by_subsystem.values())

    score = calculate_readiness_score(check_statuses)
    cert_status = _certification_status(score, check_statuses)
    notes = encode_scoped_notes(
        owner_user_id=owner_user_id,
        summary=f"Production certification {cert_status} with readiness score {score}.",
        check_statuses=check_statuses,
    )
    row = ProductionCertification(
        certification_status=cert_status,
        readiness_score=score,
        certification_notes=notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_certification_read(row)


def generate_go_live_assessment(
    session: Session,
    *,
    owner_user_id: int,
    certification: ProductionCertificationRead,
) -> GoLiveAssessmentRead:
    assessment_status = _go_live_status(certification.certification_status, certification.readiness_score)
    summary = encode_scoped_notes(
        owner_user_id=owner_user_id,
        summary=(
            f"Go-live assessment {assessment_status} for Oakley personal production use "
            f"(score {certification.readiness_score}, certification {certification.certification_status})."
        ),
        certification_uuid=certification.certification_uuid,
    )
    row = GoLiveAssessment(
        assessment_status=assessment_status,
        overall_score=certification.readiness_score,
        assessment_summary=summary,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_assessment_read(row)


def list_certifications_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProductionCertificationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ProductionCertification).order_by(
            ProductionCertification.certified_at.desc(),
            ProductionCertification.id.desc(),
        )
    ).all()
    filtered = [row for row in rows if notes_owner_user_id(row.certification_notes) == owner_user_id]
    page = filtered[offset : offset + limit]
    return [_to_certification_read(row) for row in page], len(filtered)


def list_assessments_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GoLiveAssessmentRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GoLiveAssessment).order_by(GoLiveAssessment.assessed_at.desc(), GoLiveAssessment.id.desc())
    ).all()
    filtered = [row for row in rows if notes_owner_user_id(row.assessment_summary) == owner_user_id]
    page = filtered[offset : offset + limit]
    return [_to_assessment_read(row) for row in page], len(filtered)


def build_production_readiness_dashboard(session: Session, *, owner_user_id: int) -> ProductionReadinessDashboardRead:
    from app.services.production_readiness import latest_subsystem_statuses

    statuses = latest_subsystem_statuses(session, owner_user_id=owner_user_id)
    checklist_pass, checklist_total = latest_checklist_summary_for_owner(session, owner_user_id=owner_user_id)
    certifications, _ = list_certifications_for_owner(session, owner_user_id=owner_user_id, limit=1, offset=0)
    assessments, _ = list_assessments_for_owner(session, owner_user_id=owner_user_id, limit=1, offset=0)
    latest_cert = certifications[0] if certifications else None
    latest_assessment = assessments[0] if assessments else None

    subsystem_statuses = [
        statuses.get("marketplace", CHECK_STATUS_WARNING),
        statuses.get("forecast", CHECK_STATUS_WARNING),
        statuses.get("data_protection", CHECK_STATUS_WARNING),
        statuses.get("operations", CHECK_STATUS_WARNING),
        statuses.get("agent_platform", CHECK_STATUS_WARNING),
    ]
    score = latest_cert.readiness_score if latest_cert else calculate_readiness_score(subsystem_statuses)
    cert_status = latest_cert.certification_status if latest_cert else "PENDING"
    go_live = latest_assessment.assessment_status if latest_assessment else "PENDING"

    return ProductionReadinessDashboardRead(
        readiness_score=score,
        certification_status=cert_status,
        marketplace_status=statuses.get("marketplace", "PENDING"),
        forecast_status=statuses.get("forecast", "PENDING"),
        data_protection_status=statuses.get("data_protection", "PENDING"),
        operations_status=statuses.get("operations", "PENDING"),
        agent_platform_status=statuses.get("agent_platform", "PENDING"),
        checklist_pass_count=checklist_pass,
        checklist_total=checklist_total,
        go_live_status=go_live,
        latest_certification=latest_cert,
        latest_assessment=latest_assessment,
    )
