"""P44-08 `/api/v1/organizations/*/mobile-analytics` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.mobile_analytics_service import (
    build_mobile_analytics_dashboard,
    generate_mobile_analytics_snapshot,
    list_mobile_analytics_snapshots,
    list_mobile_usage_metrics,
    list_mobile_usage_trends,
)

mobile_analytics_v1_router = APIRouter(prefix="/api/v1", tags=["Mobile Analytics API v1 (P44-08)"])


def attach_mobile_analytics_layer(app: FastAPI) -> None:
    app.include_router(mobile_analytics_v1_router)


@mobile_analytics_v1_router.get("/organizations/{organization_id}/mobile-analytics", response_model=ScanApiV1Envelope)
def v1_get_mobile_analytics_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_mobile_analytics_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@mobile_analytics_v1_router.get("/organizations/{organization_id}/mobile-analytics/metrics", response_model=ScanApiV1Envelope)
def v1_list_mobile_usage_metrics(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_mobile_usage_metrics(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_analytics_v1_router.get("/organizations/{organization_id}/mobile-analytics/trends", response_model=ScanApiV1Envelope)
def v1_list_mobile_usage_trends(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_mobile_usage_trends(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_analytics_v1_router.get("/organizations/{organization_id}/mobile-analytics/snapshots", response_model=ScanApiV1Envelope)
def v1_list_mobile_analytics_snapshots(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_mobile_analytics_snapshots(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_analytics_v1_router.post(
    "/organizations/{organization_id}/mobile-analytics/generate",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_generate_mobile_analytics(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    snapshot = generate_mobile_analytics_snapshot(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    body = build_mobile_analytics_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=snapshot.id)
