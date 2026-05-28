"""P41-06 `/api/v1/automation/notifications*` notification routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from sqlmodel import Session
from starlette.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.automation_notifications import AutomationNotificationCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.automation_notifications import (
    acknowledge_alert,
    create_notification,
    get_automation_notification_owner,
    list_automation_alerts_ops,
    list_automation_alerts_owner,
    list_automation_delivery_failures_ops,
    list_automation_notification_issues_ops,
    list_automation_notification_issues_owner,
    list_automation_notification_preferences_owner,
    list_automation_notifications_ops,
    list_automation_notifications_owner,
)

automation_notifications_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Notifications API v1 (P41)"])


def _is_automation_notifications_v1_path(path: str) -> bool:
    return (
        path.startswith("/api/v1/automation/notifications")
        or path.startswith("/api/v1/automation/alerts")
        or path.startswith("/api/v1/automation/preferences")
        or path.startswith("/api/v1/automation/notification/")
        or path.startswith("/api/v1/ops/automation/notifications")
        or path.startswith("/api/v1/ops/automation/alerts")
        or path.startswith("/api/v1/ops/automation/notification/")
        or path.startswith("/api/v1/ops/automation/delivery-failures")
    )


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_notifications_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_notifications_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_notifications_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_notifications_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_notifications_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_notifications_v1_router)


@automation_notifications_v1_router.get("/automation/notifications", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_notifications(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_notifications_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_notifications_v1_router.get("/automation/notifications/{notification_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_notification(
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_notification_owner(session, owner_user_id=int(current_user.id), notification_id=notification_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.notification_checksum)


@automation_notifications_v1_router.get("/automation/alerts", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_alerts_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_notifications_v1_router.get("/automation/preferences", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_preferences(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_notification_preferences_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_notifications_v1_router.get("/automation/notification/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_notification_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_notification_issues_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_notifications_v1_router.post("/ops/automation/notifications/create", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_create_notification(
    payload: AutomationNotificationCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body, created = create_notification(session, settings, owner_user_id=int(current_user.id or 0), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.notification_checksum)


@automation_notifications_v1_router.post("/ops/automation/alerts/{alert_id}/acknowledge", response_model=ScanApiV1Envelope)
def v1_ops_acknowledge_alert(
    alert_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = acknowledge_alert(session, alert_id=alert_id)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.alert_checksum)


@automation_notifications_v1_router.get("/ops/automation/notifications", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_notifications(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_notifications_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_notifications_v1_router.get("/ops/automation/alerts", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_alerts_ops(session, limit=limit, offset=offset, critical_only=False)
    return wrap_standard_list(body, owner_user_id=None)


@automation_notifications_v1_router.get("/ops/automation/alerts/critical", response_model=ScanApiV1Envelope)
def v1_ops_list_critical_automation_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_alerts_ops(session, limit=limit, offset=offset, critical_only=True)
    return wrap_standard_list(body, owner_user_id=None)


@automation_notifications_v1_router.get("/ops/automation/notification/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_notification_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_notification_issues_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_notifications_v1_router.get("/ops/automation/delivery-failures", response_model=ScanApiV1Envelope)
def v1_ops_list_delivery_failures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_delivery_failures_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)
