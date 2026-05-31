from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.data_integrity import DataIntegrityCheck
from app.models.operations_reliability import PlatformHealthCheck
from app.schemas.operations_reliability import PlatformHealthCheckRead
from app.services.agent_dashboard import get_agent_status_summary
from app.services.forecast_platform_health import get_forecast_platform_health
from app.services.marketplace_health import get_marketplace_health


def _health_score(status: str) -> float:
    mapping = {"HEALTHY": 100.0, "WARNING": 70.0, "FAILED": 30.0, "DISABLED": 50.0, "PASS": 100.0}
    return mapping.get(status, 60.0)


def _persist_check(
    session: Session,
    *,
    owner_user_id: int,
    subsystem: str,
    health_status: str,
    check_payload_json: dict,
) -> PlatformHealthCheckRead:
    row = PlatformHealthCheck(
        subsystem=subsystem,
        health_status=health_status,
        health_score=_health_score(health_status),
        check_payload_json={**check_payload_json, "owner_user_id": owner_user_id},
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return PlatformHealthCheckRead.model_validate(row)


def check_marketplace_health(session: Session, *, owner_user_id: int) -> PlatformHealthCheckRead:
    health = get_marketplace_health(session, owner_id=owner_user_id)
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        subsystem="marketplace",
        health_status=health.overall_status,
        check_payload_json={"components": [component.model_dump(mode="json") for component in health.components]},
    )


def check_forecast_health(session: Session, *, owner_user_id: int) -> PlatformHealthCheckRead:
    health = get_forecast_platform_health(session, owner_user_id=owner_user_id)
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        subsystem="forecast",
        health_status=health.overall_status,
        check_payload_json={"components": [component.model_dump(mode="json") for component in health.components]},
    )


def check_agent_health(session: Session, *, owner_user_id: int) -> PlatformHealthCheckRead:
    agents = get_agent_status_summary(session, owner_user_id=owner_user_id, limit=200, offset=0).items
    statuses = [row.health_status for row in agents if row.health_status]
    if any(status == "FAILED" for status in statuses):
        overall = "FAILED"
    elif any(status == "WARNING" for status in statuses):
        overall = "WARNING"
    elif not statuses:
        overall = "WARNING"
    else:
        overall = "HEALTHY"
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        subsystem="agents",
        health_status=overall,
        check_payload_json={"agent_count": len(agents), "agents": [row.model_dump(mode="json") for row in agents[:20]]},
    )


def check_data_protection_health(session: Session, *, owner_user_id: int) -> PlatformHealthCheckRead:
    latest = session.exec(
        select(DataIntegrityCheck)
        .where(DataIntegrityCheck.owner_user_id == owner_user_id)
        .order_by(DataIntegrityCheck.checked_at.desc(), DataIntegrityCheck.id.desc())
    ).first()
    if latest is None:
        status = "WARNING"
        payload: dict = {"integrity_check_id": None, "summary": "No integrity checks recorded yet."}
    else:
        status = "HEALTHY" if latest.check_status == "PASS" else "WARNING"
        payload = {"integrity_check_id": latest.id, "check_status": latest.check_status, "summary_json": latest.summary_json}
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        subsystem="data_protection",
        health_status=status,
        check_payload_json=payload,
    )


def check_database_health(session: Session, *, owner_user_id: int) -> PlatformHealthCheckRead:
    try:
        session.exec(text("SELECT 1")).one()
        status = "HEALTHY"
        payload = {"connectivity": "ok"}
    except Exception as exc:  # pragma: no cover - defensive
        status = "FAILED"
        payload = {"connectivity": "failed", "error": str(exc)}
    return _persist_check(
        session,
        owner_user_id=owner_user_id,
        subsystem="database",
        health_status=status,
        check_payload_json=payload,
    )


def check_platform_health(session: Session, *, owner_user_id: int) -> list[PlatformHealthCheckRead]:
    return [
        check_marketplace_health(session, owner_user_id=owner_user_id),
        check_forecast_health(session, owner_user_id=owner_user_id),
        check_agent_health(session, owner_user_id=owner_user_id),
        check_data_protection_health(session, owner_user_id=owner_user_id),
        check_database_health(session, owner_user_id=owner_user_id),
    ]


def _owner_matches(row_owner: object, owner_user_id: int) -> bool:
    if row_owner is None:
        return False
    return int(row_owner) == owner_user_id


def list_health_checks_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[PlatformHealthCheckRead]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(select(PlatformHealthCheck).order_by(PlatformHealthCheck.checked_at.desc(), PlatformHealthCheck.id.desc())).all()
    filtered = [
        PlatformHealthCheckRead.model_validate(row)
        for row in rows
        if _owner_matches(row.check_payload_json.get("owner_user_id"), owner_user_id)
    ]
    return filtered[offset : offset + limit]
