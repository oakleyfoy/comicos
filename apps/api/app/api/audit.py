from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.dependencies.organization_auth import resolve_org_context
from app.db.session import get_session
from app.schemas.organization_audit import AuditCategory, ComplianceSeverityLevel
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_standard_list
from app.security.tenant_context import OrganizationActorContext
from app.services.audit_ledger_service import (
    list_org_audit_access_logs,
    list_org_audit_entries,
    list_org_compliance_events,
)

audit_v1_router = APIRouter(prefix="/api/v1", tags=["Organization Audit API v1 (P42-08)"])


def attach_audit_layer(app: FastAPI) -> None:
    app.include_router(audit_v1_router)


@audit_v1_router.get("/organizations/{organization_id}/audit", response_model=ScanApiV1Envelope)
def v1_list_org_audit_entries(
    organization_id: int,
    session: Session = Depends(get_session),
    context: OrganizationActorContext = Depends(resolve_org_context),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: AuditCategory | None = Query(default=None),
    actor: int | None = Query(default=None, ge=1),
    resource_type: str | None = Query(default=None),
) -> ScanApiV1Envelope:
    body = list_org_audit_entries(
        session,
        organization_id=organization_id,
        actor_user_id=context.actor_user_id,
        limit=limit,
        offset=offset,
        audit_category=category,
        actor_filter_user_id=actor,
        resource_type=resource_type,
    )
    return wrap_standard_list(body, owner_user_id=context.actor_user_id)


@audit_v1_router.get("/organizations/{organization_id}/compliance-events", response_model=ScanApiV1Envelope)
def v1_list_org_compliance_events(
    organization_id: int,
    session: Session = Depends(get_session),
    context: OrganizationActorContext = Depends(resolve_org_context),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    severity: ComplianceSeverityLevel | None = Query(default=None),
) -> ScanApiV1Envelope:
    body = list_org_compliance_events(
        session,
        organization_id=organization_id,
        actor_user_id=context.actor_user_id,
        limit=limit,
        offset=offset,
        severity_level=severity,
    )
    return wrap_standard_list(body, owner_user_id=context.actor_user_id)


@audit_v1_router.get("/organizations/{organization_id}/audit/access-log", response_model=ScanApiV1Envelope)
def v1_list_org_audit_access_log(
    organization_id: int,
    session: Session = Depends(get_session),
    context: OrganizationActorContext = Depends(resolve_org_context),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: int | None = Query(default=None, ge=1),
    resource_type: str | None = Query(default=None),
) -> ScanApiV1Envelope:
    body = list_org_audit_access_logs(
        session,
        organization_id=organization_id,
        actor_user_id=context.actor_user_id,
        limit=limit,
        offset=offset,
        actor_filter_user_id=actor,
        resource_type=resource_type,
    )
    return wrap_standard_list(body, owner_user_id=context.actor_user_id)
