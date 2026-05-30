from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import AgentCapability, AgentDefinition, AgentExecution, AgentPermissionAuditEvent, AgentPermissionPolicy
from app.schemas.agent_security import (
    AgentPermissionAuditEventListResponse,
    AgentPermissionAuditEventRead,
    AgentPermissionCheckRead,
    AgentPermissionPolicyCreate,
    AgentPermissionPolicyListResponse,
    AgentPermissionPolicyRead,
)
from app.services.agent_registry import clamp_agent_pagination

PERMISSION_SCOPE_READ = "read"
PERMISSION_SCOPE_WRITE = "write"
PERMISSION_SCOPE_EXECUTE = "execute"
PERMISSION_SCOPE_REVIEW = "review"
PERMISSION_SCOPE_ADMIN = "admin"

ALLOWED_PERMISSION_SCOPES = {
    PERMISSION_SCOPE_READ,
    PERMISSION_SCOPE_WRITE,
    PERMISSION_SCOPE_EXECUTE,
    PERMISSION_SCOPE_REVIEW,
    PERMISSION_SCOPE_ADMIN,
}

DECISION_ALLOWED = "allowed"
DECISION_DENIED = "denied"

EXECUTE_PERMISSION_CAPABILITY = "agent.execute"
RECOMMENDATION_REVIEW_CAPABILITY = "recommendation.review"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return _as_utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _normalize_scope(permission_scope: str) -> str:
    normalized = permission_scope.strip().lower()
    if normalized not in ALLOWED_PERMISSION_SCOPES:
        raise HTTPException(status_code=422, detail=f"Unsupported permission scope: {permission_scope}.")
    return normalized


def _normalize_capability_code(capability_code: str) -> str:
    normalized = capability_code.strip().lower()
    if not normalized:
        raise HTTPException(status_code=422, detail="Capability code is required.")
    return normalized


def _agent_row(session: Session, *, agent_id: int) -> AgentDefinition:
    row = session.get(AgentDefinition, agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent definition not found.")
    return row


def _execution_row(session: Session, *, execution_id: int) -> AgentExecution:
    row = session.get(AgentExecution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent execution not found.")
    return row


def _policy_row(
    session: Session,
    *,
    policy_id: int,
) -> AgentPermissionPolicy:
    row = session.get(AgentPermissionPolicy, policy_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent permission policy not found.")
    return row


def _policy_by_edge(
    session: Session,
    *,
    agent_id: int,
    capability_code: str,
    permission_scope: str,
) -> AgentPermissionPolicy | None:
    return session.exec(
        select(AgentPermissionPolicy).where(
            AgentPermissionPolicy.agent_id == agent_id,
            AgentPermissionPolicy.capability_code == capability_code,
            AgentPermissionPolicy.permission_scope == permission_scope,
        )
    ).first()


def _capability_rows(session: Session, *, agent_id: int) -> list[AgentCapability]:
    return session.exec(
        select(AgentCapability)
        .where(AgentCapability.agent_id == agent_id)
        .order_by(AgentCapability.capability_code.asc(), AgentCapability.id.asc())
    ).all()


def _known_capability_codes(session: Session, *, agent_id: int) -> set[str]:
    return {row.capability_code for row in _capability_rows(session, agent_id=agent_id)}


def _policy_read(row: AgentPermissionPolicy) -> AgentPermissionPolicyRead:
    return AgentPermissionPolicyRead(
        id=int(row.id or 0),
        agent_id=row.agent_id,
        capability_code=row.capability_code,
        permission_scope=row.permission_scope,
        allowed=row.allowed,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit_read(row: AgentPermissionAuditEvent) -> AgentPermissionAuditEventRead:
    return AgentPermissionAuditEventRead(
        id=int(row.id or 0),
        agent_id=row.agent_id,
        execution_id=row.execution_id,
        capability_code=row.capability_code,
        action_code=row.action_code,
        decision=row.decision,
        reason=row.reason,
        event_payload_json=row.event_payload_json,
        created_at=row.created_at,
    )


def grant_permission(session: Session, *, payload: AgentPermissionPolicyCreate) -> AgentPermissionPolicyRead:
    _agent_row(session, agent_id=payload.agent_id)
    capability_code = _normalize_capability_code(payload.capability_code)
    permission_scope = _normalize_scope(payload.permission_scope)
    now = utc_now()
    existing = _policy_by_edge(
        session,
        agent_id=payload.agent_id,
        capability_code=capability_code,
        permission_scope=permission_scope,
    )
    if existing is None:
        row = AgentPermissionPolicy(
            agent_id=payload.agent_id,
            capability_code=capability_code,
            permission_scope=permission_scope,
            allowed=payload.allowed,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        existing.allowed = payload.allowed
        existing.updated_at = now
        session.add(existing)
        row = existing
    session.commit()
    session.refresh(row)
    return _policy_read(row)


def revoke_permission(session: Session, *, policy_id: int) -> None:
    row = _policy_row(session, policy_id=policy_id)
    session.delete(row)
    session.commit()


def list_agent_permissions(
    session: Session,
    *,
    agent_id: int | None = None,
    capability_code: str | None = None,
    permission_scope: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AgentPermissionPolicyListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    filters = []
    if agent_id is not None:
        filters.append(AgentPermissionPolicy.agent_id == agent_id)
    if capability_code is not None:
        filters.append(AgentPermissionPolicy.capability_code == _normalize_capability_code(capability_code))
    if permission_scope is not None:
        filters.append(AgentPermissionPolicy.permission_scope == _normalize_scope(permission_scope))
    total_items = int(session.exec(select(func.count()).select_from(AgentPermissionPolicy).where(*filters)).one())
    rows = session.exec(
        select(AgentPermissionPolicy)
        .where(*filters)
        .order_by(
            AgentPermissionPolicy.agent_id.asc(),
            AgentPermissionPolicy.capability_code.asc(),
            AgentPermissionPolicy.permission_scope.asc(),
            AgentPermissionPolicy.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return AgentPermissionPolicyListResponse(
        items=[_policy_read(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def audit_permission_decision(
    session: Session,
    *,
    agent_id: int,
    execution_id: int | None,
    capability_code: str,
    action_code: str,
    decision: str,
    reason: str,
    event_payload_json: dict[str, Any] | None = None,
) -> AgentPermissionAuditEventRead:
    _agent_row(session, agent_id=agent_id)
    if execution_id is not None:
        _execution_row(session, execution_id=execution_id)
    normalized_decision = decision.strip().lower()
    if normalized_decision not in {DECISION_ALLOWED, DECISION_DENIED}:
        raise HTTPException(status_code=422, detail=f"Unsupported permission decision: {decision}.")
    row = AgentPermissionAuditEvent(
        agent_id=agent_id,
        execution_id=execution_id,
        capability_code=_normalize_capability_code(capability_code),
        action_code=action_code.strip().lower(),
        decision=normalized_decision,
        reason=reason.strip(),
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _audit_read(row)


def list_permission_audit_events(
    session: Session,
    *,
    agent_id: int | None = None,
    decision: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AgentPermissionAuditEventListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    filters = []
    if agent_id is not None:
        filters.append(AgentPermissionAuditEvent.agent_id == agent_id)
    if decision is not None:
        filters.append(AgentPermissionAuditEvent.decision == decision.strip().lower())
    total_items = int(session.exec(select(func.count()).select_from(AgentPermissionAuditEvent).where(*filters)).one())
    rows = session.exec(
        select(AgentPermissionAuditEvent)
        .where(*filters)
        .order_by(AgentPermissionAuditEvent.created_at.desc(), AgentPermissionAuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AgentPermissionAuditEventListResponse(
        items=[_audit_read(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def _permission_denial(
    *,
    agent_id: int,
    execution_id: int | None,
    capability_code: str,
    permission_scope: str,
    action_code: str,
    reason: str,
) -> AgentPermissionCheckRead:
    return AgentPermissionCheckRead(
        agent_id=agent_id,
        execution_id=execution_id,
        capability_code=capability_code,
        permission_scope=permission_scope,
        action_code=action_code,
        allowed=False,
        decision=DECISION_DENIED,
        reason=reason,
    )


def check_permission(
    session: Session,
    *,
    agent_id: int,
    capability_code: str,
    permission_scope: str,
    action_code: str,
    execution_id: int | None = None,
    event_payload_json: dict[str, Any] | None = None,
    audit_denied: bool = True,
) -> AgentPermissionCheckRead:
    _agent_row(session, agent_id=agent_id)
    normalized_capability_code = _normalize_capability_code(capability_code)
    normalized_scope = _normalize_scope(permission_scope)
    normalized_action_code = action_code.strip().lower()
    known_capabilities = _known_capability_codes(session, agent_id=agent_id)
    synthetic_capabilities = {EXECUTE_PERMISSION_CAPABILITY, RECOMMENDATION_REVIEW_CAPABILITY}
    if normalized_capability_code not in known_capabilities and normalized_capability_code not in synthetic_capabilities:
        result = _permission_denial(
            agent_id=agent_id,
            execution_id=execution_id,
            capability_code=normalized_capability_code,
            permission_scope=normalized_scope,
            action_code=normalized_action_code,
            reason="unknown_capability",
        )
        if audit_denied:
            audit_permission_decision(
                session,
                agent_id=agent_id,
                execution_id=execution_id,
                capability_code=normalized_capability_code,
                action_code=normalized_action_code,
                decision=DECISION_DENIED,
                reason=result.reason,
                event_payload_json=event_payload_json,
            )
        return result
    row = _policy_by_edge(
        session,
        agent_id=agent_id,
        capability_code=normalized_capability_code,
        permission_scope=normalized_scope,
    )
    if row is None:
        result = _permission_denial(
            agent_id=agent_id,
            execution_id=execution_id,
            capability_code=normalized_capability_code,
            permission_scope=normalized_scope,
            action_code=normalized_action_code,
            reason="missing_policy",
        )
        if audit_denied:
            audit_permission_decision(
                session,
                agent_id=agent_id,
                execution_id=execution_id,
                capability_code=normalized_capability_code,
                action_code=normalized_action_code,
                decision=DECISION_DENIED,
                reason=result.reason,
                event_payload_json=event_payload_json,
            )
        return result
    if not row.allowed:
        result = _permission_denial(
            agent_id=agent_id,
            execution_id=execution_id,
            capability_code=normalized_capability_code,
            permission_scope=normalized_scope,
            action_code=normalized_action_code,
            reason="policy_denied",
        )
        if audit_denied:
            audit_permission_decision(
                session,
                agent_id=agent_id,
                execution_id=execution_id,
                capability_code=normalized_capability_code,
                action_code=normalized_action_code,
                decision=DECISION_DENIED,
                reason=result.reason,
                event_payload_json=event_payload_json,
            )
        return result
    return AgentPermissionCheckRead(
        agent_id=agent_id,
        execution_id=execution_id,
        capability_code=normalized_capability_code,
        permission_scope=normalized_scope,
        action_code=normalized_action_code,
        allowed=True,
        decision=DECISION_ALLOWED,
        reason="policy_allowed",
    )
