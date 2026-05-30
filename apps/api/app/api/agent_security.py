"""Permission policy and audit routes for the agent guardrail layer."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.agent_security import AgentPermissionCheckRequest, AgentPermissionPolicyCreate, AgentPermissionPolicyDeleteRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.agent_permissions import (
    check_permission,
    grant_permission,
    list_agent_permissions,
    list_permission_audit_events,
    revoke_permission,
)
from app.services.ops_admin import ensure_ops_admin_access

agent_security_v1_router = APIRouter(prefix="/api/v1", tags=["Agent Security API v1"])


def attach_agent_security_layer(app: FastAPI) -> None:
    app.include_router(agent_security_v1_router)


@agent_security_v1_router.get("/agent-security/policies", response_model=ScanApiV1Envelope)
def v1_list_agent_security_policies(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    agent_id: int | None = Query(default=None),
    capability_code: str | None = Query(default=None),
    permission_scope: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_agent_permissions(
        session,
        agent_id=agent_id,
        capability_code=capability_code,
        permission_scope=permission_scope,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id or 0))


@agent_security_v1_router.post("/agent-security/policies", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_agent_security_policy(
    payload: AgentPermissionPolicyCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = grant_permission(session, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id or 0), snapshot_id=body.id)


@agent_security_v1_router.delete("/agent-security/policies/{policy_id}", response_model=ScanApiV1Envelope)
def v1_delete_agent_security_policy(
    policy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    revoke_permission(session, policy_id=policy_id)
    body = AgentPermissionPolicyDeleteRead(policy_id=policy_id, deleted=True)
    return wrap_object(body, owner_user_id=int(current_user.id or 0))


@agent_security_v1_router.get("/agent-security/audit-events", response_model=ScanApiV1Envelope)
def v1_list_agent_security_audit_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    agent_id: int | None = Query(default=None),
    decision: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_permission_audit_events(
        session,
        agent_id=agent_id,
        decision=decision,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id or 0))


@agent_security_v1_router.post("/agent-security/check", response_model=ScanApiV1Envelope)
def v1_check_agent_security_permission(
    payload: AgentPermissionCheckRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    body = check_permission(
        session,
        agent_id=payload.agent_id,
        execution_id=payload.execution_id,
        capability_code=payload.capability_code,
        permission_scope=payload.permission_scope,
        action_code=payload.action_code,
        event_payload_json={
            **payload.event_payload_json,
            "checked_by_user_id": int(current_user.id or 0),
        },
    )
    return wrap_object(body, owner_user_id=int(current_user.id or 0))
