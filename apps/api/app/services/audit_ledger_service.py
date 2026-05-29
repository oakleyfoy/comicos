from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    OrganizationAuditAccessLog,
    OrganizationAuditLedger,
    OrganizationComplianceEvent,
)
from app.schemas.organization_audit import (
    AUDIT_CATEGORIES,
    LINEAGE_COMPLIANCE_PREFIX,
    SEVERITY_LEVELS,
    OrganizationAuditAccessLogListResponse,
    OrganizationAuditAccessLogResponse,
    OrganizationAuditLedgerListResponse,
    OrganizationAuditLedgerResponse,
    OrganizationComplianceEventListResponse,
    OrganizationComplianceEventResponse,
)
from app.security.tenant_context import get_membership_record, get_organization_or_404
from app.services.authorization_service import evaluate_permission

ENGINE_VERSION = "P42-08-v1"
AUDIT_VIEW_PERMISSION = "audit:view"
ACCESS_GRANTED = "GRANTED"
ACCESS_DENIED = "DENIED"
ACTIVE_ORGANIZATION_STATUS = "ACTIVE"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(_json_safe(payload), sort_keys=True))


def _normalize_resource_id(resource_id: int | str | None) -> str | None:
    if resource_id is None:
        return None
    return str(resource_id)


def _append_compliance_event(
    session: Session,
    *,
    organization_id: int,
    compliance_event_type: str,
    severity_level: str,
    event_payload_json: dict[str, Any] | None = None,
) -> OrganizationComplianceEvent:
    row = OrganizationComplianceEvent(
        organization_id=organization_id,
        compliance_event_type=compliance_event_type,
        severity_level=severity_level,
        event_payload_json=_stable_payload(event_payload_json or {}),
    )
    session.add(row)
    session.flush()
    return row


def _append_lineage_compliance_event(
    session: Session,
    *,
    organization_id: int,
    lineage_type: str,
    severity_level: str,
    payload: dict[str, Any] | None = None,
) -> OrganizationComplianceEvent:
    return _append_compliance_event(
        session,
        organization_id=organization_id,
        compliance_event_type=f"{LINEAGE_COMPLIANCE_PREFIX}{lineage_type}",
        severity_level=severity_level,
        event_payload_json=payload,
    )


def _to_audit_entry_response(row: OrganizationAuditLedger) -> OrganizationAuditLedgerResponse:
    assert row.id is not None
    return OrganizationAuditLedgerResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        actor_user_id=row.actor_user_id,
        audit_category=str(row.audit_category),
        audit_action=str(row.audit_action),
        resource_type=str(row.resource_type),
        resource_id=row.resource_id,
        audit_payload_json=dict(row.audit_payload_json or {}),
        created_at=row.created_at,
    )


def _to_compliance_event_response(row: OrganizationComplianceEvent) -> OrganizationComplianceEventResponse:
    assert row.id is not None
    return OrganizationComplianceEventResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        compliance_event_type=str(row.compliance_event_type),
        severity_level=str(row.severity_level),
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _to_access_log_response(row: OrganizationAuditAccessLog) -> OrganizationAuditAccessLogResponse:
    assert row.id is not None
    return OrganizationAuditAccessLogResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        actor_user_id=int(row.actor_user_id),
        accessed_resource_type=str(row.accessed_resource_type),
        accessed_resource_id=row.accessed_resource_id,
        access_result=str(row.access_result),
        created_at=row.created_at,
    )


def create_audit_entry(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    audit_category: str,
    audit_action: str,
    resource_type: str,
    resource_id: int | str | None = None,
    audit_payload_json: dict[str, Any] | None = None,
) -> OrganizationAuditLedger:
    if audit_category not in AUDIT_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unsupported audit category.")
    payload = dict(audit_payload_json or {})
    payload["engine_version"] = ENGINE_VERSION
    row = OrganizationAuditLedger(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_category=audit_category,
        audit_action=audit_action,
        resource_type=resource_type,
        resource_id=_normalize_resource_id(resource_id),
        audit_payload_json=_stable_payload(payload),
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    _append_lineage_compliance_event(
        session,
        organization_id=organization_id,
        lineage_type="audit_entry_created",
        severity_level="info",
        payload={"audit_entry_id": int(row.id), "audit_action": audit_action, "audit_category": audit_category},
    )
    return row


def create_compliance_event(
    session: Session,
    *,
    organization_id: int,
    compliance_event_type: str,
    severity_level: str,
    event_payload_json: dict[str, Any] | None = None,
) -> OrganizationComplianceEvent:
    if severity_level not in SEVERITY_LEVELS:
        raise HTTPException(status_code=400, detail="Unsupported compliance severity.")
    payload = dict(event_payload_json or {})
    payload["engine_version"] = ENGINE_VERSION
    row = _append_compliance_event(
        session,
        organization_id=organization_id,
        compliance_event_type=compliance_event_type,
        severity_level=severity_level,
        event_payload_json=payload,
    )
    if not compliance_event_type.startswith(LINEAGE_COMPLIANCE_PREFIX):
        assert row.id is not None
        _append_lineage_compliance_event(
            session,
            organization_id=organization_id,
            lineage_type="compliance_event_created",
            severity_level="info",
            payload={"compliance_event_id": int(row.id), "compliance_event_type": compliance_event_type},
        )
        if severity_level in {"elevated", "critical"} and compliance_event_type.startswith("security."):
            _append_lineage_compliance_event(
                session,
                organization_id=organization_id,
                lineage_type="elevated_security_event",
                severity_level=severity_level,
                payload={"compliance_event_id": int(row.id), "compliance_event_type": compliance_event_type},
            )
        if severity_level == "critical":
            _append_lineage_compliance_event(
                session,
                organization_id=organization_id,
                lineage_type="critical_org_action",
                severity_level="critical",
                payload={"compliance_event_id": int(row.id), "compliance_event_type": compliance_event_type},
            )
    return row


def create_audit_access_log(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    accessed_resource_type: str,
    accessed_resource_id: int | str | None = None,
    access_result: str,
) -> OrganizationAuditAccessLog:
    row = OrganizationAuditAccessLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        accessed_resource_type=accessed_resource_type,
        accessed_resource_id=_normalize_resource_id(accessed_resource_id),
        access_result=access_result,
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    _append_lineage_compliance_event(
        session,
        organization_id=organization_id,
        lineage_type="audit_access_logged",
        severity_level="info" if access_result == ACCESS_GRANTED else "warning",
        payload={
            "audit_access_log_id": int(row.id),
            "accessed_resource_type": accessed_resource_type,
            "access_result": access_result,
        },
    )
    return row


def _record_unauthorized_audit_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    accessed_resource_type: str,
    accessed_resource_id: int | str | None,
    reason: str,
) -> None:
    audit_session = Session(session.get_bind())
    try:
        create_audit_access_log(
            audit_session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            accessed_resource_type=accessed_resource_type,
            accessed_resource_id=accessed_resource_id,
            access_result=ACCESS_DENIED,
        )
        _append_lineage_compliance_event(
            audit_session,
            organization_id=organization_id,
            lineage_type="unauthorized_audit_access_attempt",
            severity_level="warning",
            payload={
                "accessed_resource_type": accessed_resource_type,
                "accessed_resource_id": _normalize_resource_id(accessed_resource_id),
                "reason": reason,
            },
        )
        audit_session.commit()
    finally:
        audit_session.close()


def _require_audit_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    accessed_resource_type: str,
    accessed_resource_id: int | str | None = None,
) -> None:
    organization = get_organization_or_404(session, organization_id=organization_id)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        raise HTTPException(status_code=409, detail="Organization is not active.")
    member = get_membership_record(session, organization_id=organization_id, user_id=actor_user_id, active_only=True)
    if member is None:
        _record_unauthorized_audit_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            accessed_resource_type=accessed_resource_type,
            accessed_resource_id=accessed_resource_id,
            reason="membership_required",
        )
        raise HTTPException(status_code=403, detail="Organization audit access denied.")
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=AUDIT_VIEW_PERMISSION,
        evaluation_context_json={"accessed_resource_type": accessed_resource_type},
    )
    if not evaluation.allowed:
        _record_unauthorized_audit_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            accessed_resource_type=accessed_resource_type,
            accessed_resource_id=accessed_resource_id,
            reason=evaluation.reason,
        )
        raise HTTPException(status_code=403, detail="Organization audit access denied.")
    create_audit_access_log(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        accessed_resource_type=accessed_resource_type,
        accessed_resource_id=accessed_resource_id,
        access_result=ACCESS_GRANTED,
    )
    session.commit()


def list_org_audit_entries(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    audit_category: str | None = None,
    actor_filter_user_id: int | None = None,
    resource_type: str | None = None,
) -> OrganizationAuditLedgerListResponse:
    _require_audit_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        accessed_resource_type="audit_ledger",
        accessed_resource_id=organization_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    if audit_category is not None and audit_category not in AUDIT_CATEGORIES:
        raise HTTPException(status_code=400, detail="Unsupported audit category.")
    stmt = select(OrganizationAuditLedger).where(OrganizationAuditLedger.organization_id == organization_id)
    count_stmt = select(func.count()).select_from(OrganizationAuditLedger).where(
        OrganizationAuditLedger.organization_id == organization_id
    )
    if audit_category is not None:
        stmt = stmt.where(OrganizationAuditLedger.audit_category == audit_category)
        count_stmt = count_stmt.where(OrganizationAuditLedger.audit_category == audit_category)
    if actor_filter_user_id is not None:
        stmt = stmt.where(OrganizationAuditLedger.actor_user_id == actor_filter_user_id)
        count_stmt = count_stmt.where(OrganizationAuditLedger.actor_user_id == actor_filter_user_id)
    if resource_type is not None:
        stmt = stmt.where(OrganizationAuditLedger.resource_type == resource_type)
        count_stmt = count_stmt.where(OrganizationAuditLedger.resource_type == resource_type)
    rows = session.exec(
        stmt.order_by(OrganizationAuditLedger.created_at.desc(), OrganizationAuditLedger.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(count_stmt).one()
    return OrganizationAuditLedgerListResponse(
        items=[_to_audit_entry_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_org_compliance_events(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    severity_level: str | None = None,
) -> OrganizationComplianceEventListResponse:
    _require_audit_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        accessed_resource_type="compliance_events",
        accessed_resource_id=organization_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    if severity_level is not None and severity_level not in SEVERITY_LEVELS:
        raise HTTPException(status_code=400, detail="Unsupported compliance severity.")
    stmt = (
        select(OrganizationComplianceEvent)
        .where(OrganizationComplianceEvent.organization_id == organization_id)
        .where(~OrganizationComplianceEvent.compliance_event_type.like(f"{LINEAGE_COMPLIANCE_PREFIX}%"))
    )
    count_stmt = (
        select(func.count())
        .select_from(OrganizationComplianceEvent)
        .where(OrganizationComplianceEvent.organization_id == organization_id)
        .where(~OrganizationComplianceEvent.compliance_event_type.like(f"{LINEAGE_COMPLIANCE_PREFIX}%"))
    )
    if severity_level is not None:
        stmt = stmt.where(OrganizationComplianceEvent.severity_level == severity_level)
        count_stmt = count_stmt.where(OrganizationComplianceEvent.severity_level == severity_level)
    rows = session.exec(
        stmt.order_by(OrganizationComplianceEvent.created_at.desc(), OrganizationComplianceEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(count_stmt).one()
    return OrganizationComplianceEventListResponse(
        items=[_to_compliance_event_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_org_audit_access_logs(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    actor_filter_user_id: int | None = None,
    resource_type: str | None = None,
) -> OrganizationAuditAccessLogListResponse:
    _require_audit_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        accessed_resource_type="audit_access_log",
        accessed_resource_id=organization_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(OrganizationAuditAccessLog).where(OrganizationAuditAccessLog.organization_id == organization_id)
    count_stmt = select(func.count()).select_from(OrganizationAuditAccessLog).where(
        OrganizationAuditAccessLog.organization_id == organization_id
    )
    if actor_filter_user_id is not None:
        stmt = stmt.where(OrganizationAuditAccessLog.actor_user_id == actor_filter_user_id)
        count_stmt = count_stmt.where(OrganizationAuditAccessLog.actor_user_id == actor_filter_user_id)
    if resource_type is not None:
        stmt = stmt.where(OrganizationAuditAccessLog.accessed_resource_type == resource_type)
        count_stmt = count_stmt.where(OrganizationAuditAccessLog.accessed_resource_type == resource_type)
    rows = session.exec(
        stmt.order_by(OrganizationAuditAccessLog.created_at.desc(), OrganizationAuditAccessLog.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(count_stmt).one()
    return OrganizationAuditAccessLogListResponse(
        items=[_to_access_log_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def resolve_audit_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    audit_entry: OrganizationAuditLedger,
) -> bool:
    if int(audit_entry.organization_id) != organization_id:
        return False
    try:
        _require_audit_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            accessed_resource_type="audit_entry",
            accessed_resource_id=int(audit_entry.id or 0),
        )
    except HTTPException:
        return False
    return True
