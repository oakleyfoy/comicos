from __future__ import annotations

from sqlmodel import Session, select

from app.models.data_integrity import DataIntegrityCheck, MigrationSafetyCheck
from app.models.production_readiness import ProductionReadinessCheck
from app.schemas.production_readiness import ProductionReadinessCheckRead
from app.services.agent_platform_validation import validate_platform as validate_agent_platform_core
from app.services.forecast_platform_validation import validate_forecast_platform
from app.services.marketplace_validation import validate_marketplace_platform
from app.services.production_readiness_notes import encode_scoped_notes, notes_owner_user_id, notes_summary
from app.services.recovery_recommendations import build_operations_summary

CHECK_STATUS_PASS = "PASS"
CHECK_STATUS_WARNING = "WARNING"
CHECK_STATUS_FAIL = "FAIL"


def _persist_check(
    session: Session,
    *,
    owner_user_id: int,
    check_name: str,
    subsystem: str,
    check_status: str,
    summary: str,
) -> ProductionReadinessCheckRead:
    row = ProductionReadinessCheck(
        check_name=check_name,
        subsystem=subsystem,
        check_status=check_status,
        check_notes=encode_scoped_notes(owner_user_id=owner_user_id, summary=summary),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(row)


def _to_read(row: ProductionReadinessCheck) -> ProductionReadinessCheckRead:
    data = row.model_dump()
    data["check_notes"] = notes_summary(row.check_notes)
    return ProductionReadinessCheckRead.model_validate(data)


def validate_marketplace_platform_readiness(session: Session, *, owner_user_id: int) -> ProductionReadinessCheckRead:
    validation = validate_marketplace_platform(session, owner_id=owner_user_id)
    status = validation.overall_status
    summary = f"Marketplace validation {status}; platform_certified={validation.platform_certified}."
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        check_name="Marketplace Platform Validation",
        subsystem="marketplace",
        check_status=status,
        summary=summary,
    )


def validate_forecast_platform_readiness(session: Session, *, owner_user_id: int) -> ProductionReadinessCheckRead:
    validation = validate_forecast_platform(session, owner_user_id=owner_user_id)
    status = validation.overall_status
    summary = f"Forecast platform validation {status}; platform_certified={validation.platform_certified}."
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        check_name="Forecast Platform Validation",
        subsystem="forecast",
        check_status=status,
        summary=summary,
    )


def validate_data_protection_platform(session: Session, *, owner_user_id: int) -> ProductionReadinessCheckRead:
    latest = session.exec(
        select(DataIntegrityCheck)
        .where(DataIntegrityCheck.owner_user_id == owner_user_id)
        .order_by(DataIntegrityCheck.created_at.desc(), DataIntegrityCheck.id.desc())
    ).first()
    migration = session.exec(
        select(MigrationSafetyCheck)
        .where(MigrationSafetyCheck.owner_user_id == owner_user_id)
        .order_by(MigrationSafetyCheck.created_at.desc(), MigrationSafetyCheck.id.desc())
    ).first()

    status = CHECK_STATUS_PASS
    if latest is None and migration is None:
        status = CHECK_STATUS_WARNING
    elif latest is not None and latest.check_status == "FAIL":
        status = CHECK_STATUS_FAIL
    elif migration is not None and migration.check_status == "FAIL":
        status = CHECK_STATUS_FAIL
    elif (latest is not None and latest.check_status == "WARNING") or (
        migration is not None and migration.check_status == "WARNING"
    ):
        status = CHECK_STATUS_WARNING

    summary = (
        f"Data protection review: integrity_check={None if latest is None else latest.check_status}, "
        f"migration_safety={None if migration is None else migration.check_status}."
    )
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        check_name="Data Protection Platform Validation",
        subsystem="data_protection",
        check_status=status,
        summary=summary,
    )


def validate_agent_platform(session: Session, *, owner_user_id: int) -> ProductionReadinessCheckRead:
    validation = validate_agent_platform_core(session, owner_user_id=owner_user_id)
    status = validation.overall_status
    summary = f"Agent platform validation {status} across {len(validation.checks)} checks."
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        check_name="Agent Platform Validation",
        subsystem="agent_platform",
        check_status=status,
        summary=summary,
    )


def validate_operations_platform(session: Session, *, owner_user_id: int) -> ProductionReadinessCheckRead:
    summary_read = build_operations_summary(session, owner_user_id=owner_user_id)
    platform_status = summary_read.platform_health_status
    if platform_status == "FAILED":
        status = CHECK_STATUS_FAIL
    elif platform_status == "WARNING":
        status = CHECK_STATUS_WARNING
    else:
        status = CHECK_STATUS_PASS
    summary = (
        f"Operations reliability readiness {summary_read.readiness_score}; "
        f"platform_health={platform_status}; open_issues={summary_read.open_issue_count}."
    )
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        check_name="Operations Platform Validation",
        subsystem="operations",
        check_status=status,
        summary=summary,
    )


def validate_production_readiness(session: Session, *, owner_user_id: int) -> list[ProductionReadinessCheckRead]:
    return [
        validate_marketplace_platform_readiness(session, owner_user_id=owner_user_id),
        validate_forecast_platform_readiness(session, owner_user_id=owner_user_id),
        validate_data_protection_platform(session, owner_user_id=owner_user_id),
        validate_agent_platform(session, owner_user_id=owner_user_id),
        validate_operations_platform(session, owner_user_id=owner_user_id),
    ]


def list_readiness_checks_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ProductionReadinessCheckRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ProductionReadinessCheck).order_by(
            ProductionReadinessCheck.checked_at.desc(),
            ProductionReadinessCheck.id.desc(),
        )
    ).all()
    filtered = [row for row in rows if notes_owner_user_id(row.check_notes) == owner_user_id]
    page = filtered[offset : offset + limit]
    return [_to_read(row) for row in page], len(filtered)


def latest_subsystem_statuses(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[str, str]:
    checks, _ = list_readiness_checks_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    latest: dict[str, str] = {}
    for check in checks:
        if check.subsystem not in latest:
            latest[check.subsystem] = check.check_status
    return latest


def run_production_readiness_check(session: Session, *, owner_user_id: int):
    """P57-06 go-live validation against real owner workflows and dashboards."""
    from app.services.production_readiness_validation import run_production_readiness_check as _run

    return _run(session, owner_user_id=owner_user_id)


def get_latest_production_readiness_validation(session: Session, *, owner_user_id: int):
    from app.services.production_readiness_validation import get_latest_production_readiness_run

    return get_latest_production_readiness_run(session, owner_user_id=owner_user_id)
