from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.dependencies.organization_auth import require_org_permission
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.organization_activity import ActivityCategory
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.activity_feed_service import (
    acknowledge_notification,
    list_org_activity_feed,
    list_user_notifications,
    mark_notification_read,
    unread_notification_count,
)

activity_v1_router = APIRouter(prefix="/api/v1", tags=["Organization Activity Feed API v1 (P42-07)"])


def attach_activity_layer(app: FastAPI) -> None:
    app.include_router(activity_v1_router)


@activity_v1_router.get("/organizations/{organization_id}/activity", response_model=ScanApiV1Envelope)
def v1_list_org_activity_feed(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: ActivityCategory | None = Query(default=None),
    _: object = Depends(require_org_permission("operations:view")),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_org_activity_feed(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        category=category,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@activity_v1_router.get("/organizations/{organization_id}/notifications", response_model=ScanApiV1Envelope)
def v1_list_org_notifications(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_user_notifications(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@activity_v1_router.get(
    "/organizations/{organization_id}/notifications/unread-count",
    response_model=ScanApiV1Envelope,
)
def v1_org_notification_unread_count(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = unread_notification_count(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@activity_v1_router.post(
    "/organizations/{organization_id}/notifications/{notification_id}/read",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_200_OK,
)
def v1_mark_notification_read(
    organization_id: int,
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_notification_read(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        notification_id=notification_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@activity_v1_router.post(
    "/organizations/{organization_id}/notifications/{notification_id}/acknowledge",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_200_OK,
)
def v1_acknowledge_notification(
    organization_id: int,
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = acknowledge_notification(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        notification_id=notification_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
