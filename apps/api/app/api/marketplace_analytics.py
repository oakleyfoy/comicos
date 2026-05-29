"""P43-10 `/api/v1/organizations/*/marketplace-analytics` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_analytics_service import (
    build_marketplace_analytics_dashboard,
    generate_marketplace_analytics_snapshot,
    generate_marketplace_metrics,
    generate_marketplace_trends,
    list_marketplace_metrics,
    list_marketplace_snapshots,
    list_marketplace_trends,
)

marketplace_analytics_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Analytics API v1 (P43-10)"])


def attach_marketplace_analytics_layer(app: FastAPI) -> None:
    app.include_router(marketplace_analytics_v1_router)


@marketplace_analytics_v1_router.get("/organizations/{organization_id}/marketplace-analytics", response_model=ScanApiV1Envelope)
def v1_get_marketplace_analytics_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_marketplace_analytics_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@marketplace_analytics_v1_router.get("/organizations/{organization_id}/marketplace-analytics/metrics", response_model=ScanApiV1Envelope)
def v1_list_marketplace_analytics_metrics(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_metrics(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_analytics_v1_router.get("/organizations/{organization_id}/marketplace-analytics/trends", response_model=ScanApiV1Envelope)
def v1_list_marketplace_analytics_trends(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_trends(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_analytics_v1_router.get("/organizations/{organization_id}/marketplace-analytics/snapshots", response_model=ScanApiV1Envelope)
def v1_list_marketplace_analytics_snapshots(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_snapshots(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_analytics_v1_router.post(
    "/organizations/{organization_id}/marketplace-analytics/generate",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_generate_marketplace_analytics_snapshot(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_marketplace_analytics_snapshot(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
