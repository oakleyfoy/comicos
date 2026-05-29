from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.dependencies.organization_auth import require_org_permission, resolve_org_context
from app.db.session import get_session
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.security.tenant_context import OrganizationActorContext
from app.services.dealer_dashboard_service import (
    list_dashboard_metrics,
    list_dashboard_snapshots,
    resolve_dashboard_summary,
)

dealer_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Organization Dealer Dashboard API v1 (P42-09)"])


def attach_dealer_dashboard_layer(app: FastAPI) -> None:
    app.include_router(dealer_dashboard_v1_router)


@dealer_dashboard_v1_router.get("/organizations/{organization_id}/dashboard", response_model=ScanApiV1Envelope)
def v1_get_org_dealer_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    context: OrganizationActorContext = Depends(resolve_org_context),
    refresh: bool = Query(default=True),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    body = resolve_dashboard_summary(
        session,
        organization_id=organization_id,
        actor_user_id=context.actor_user_id,
        refresh=refresh,
    )
    return wrap_object(body, owner_user_id=context.actor_user_id)


@dealer_dashboard_v1_router.get("/organizations/{organization_id}/dashboard/metrics", response_model=ScanApiV1Envelope)
def v1_list_org_dashboard_metrics(
    organization_id: int,
    session: Session = Depends(get_session),
    context: OrganizationActorContext = Depends(resolve_org_context),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    metric_period: str | None = Query(default=None),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    body = list_dashboard_metrics(
        session,
        organization_id=organization_id,
        actor_user_id=context.actor_user_id,
        limit=limit,
        offset=offset,
        metric_period=metric_period,
    )
    return wrap_standard_list(body, owner_user_id=context.actor_user_id)


@dealer_dashboard_v1_router.get("/organizations/{organization_id}/dashboard/snapshots", response_model=ScanApiV1Envelope)
def v1_list_org_dashboard_snapshots(
    organization_id: int,
    session: Session = Depends(get_session),
    context: OrganizationActorContext = Depends(resolve_org_context),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    body = list_dashboard_snapshots(
        session,
        organization_id=organization_id,
        actor_user_id=context.actor_user_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=context.actor_user_id)
