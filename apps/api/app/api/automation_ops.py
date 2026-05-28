"""P41-07 `/api/v1/automation/ops*` and ops automation dashboard routes."""

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
from app.schemas.automation_ops import AutomationOpsAuditRunCreate, AutomationOpsControlApplyCreate, AutomationOpsSnapshotCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.automation_ops import (
    apply_ops_control,
    create_ops_snapshot,
    execute_ops_audit,
    get_automation_ops_snapshot_owner,
    get_ops_system_health,
    list_automation_ops_audits,
    list_automation_ops_issues,
    list_automation_ops_metrics,
    list_automation_ops_snapshots_ops,
    list_automation_ops_snapshots_owner,
)

automation_ops_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Ops Dashboard API v1 (P41)"])


def _is_automation_ops_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation/ops") or path.startswith("/api/v1/ops/automation/")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_ops_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_ops_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_ops_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_ops_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_ops_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_ops_v1_router)


@automation_ops_v1_router.get("/automation/ops/snapshots", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_ops_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_ops_snapshots_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/automation/ops/snapshots/{snapshot_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_ops_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = get_automation_ops_snapshot_owner(session, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.id, checksum=row.snapshot_checksum)


@automation_ops_v1_router.get("/automation/ops/metrics", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_ops_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_ops_metrics(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/automation/ops/audits", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_ops_audits(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_ops_audits(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/automation/ops/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_ops_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_ops_issues(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.post("/ops/automation/snapshots/create", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_create_automation_ops_snapshot(
    payload: AutomationOpsSnapshotCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row, created = create_ops_snapshot(session, settings, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(row, owner_user_id=payload.owner_user_id, snapshot_id=row.id, checksum=row.snapshot_checksum)


@automation_ops_v1_router.post("/ops/automation/audits/run", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_run_automation_ops_audit(
    payload: AutomationOpsAuditRunCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = execute_ops_audit(session, payload=payload)
    return wrap_object(row, owner_user_id=payload.owner_user_id, checksum=row.audit_checksum)


@automation_ops_v1_router.post("/ops/automation/controls/apply", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_apply_automation_ops_control(
    payload: AutomationOpsControlApplyCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = apply_ops_control(session, payload=payload)
    return wrap_object(row, owner_user_id=payload.owner_user_id, checksum=row.control_checksum)


@automation_ops_v1_router.get("/ops/automation/snapshots", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_ops_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_ops_snapshots_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/ops/automation/metrics", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_ops_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_ops_metrics(session, owner_user_id=None, snapshot_id=snapshot_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/ops/automation/audits", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_ops_audits(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_ops_audits(session, owner_user_id=None, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/ops/automation/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_ops_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_ops_issues(session, owner_user_id=None, snapshot_id=snapshot_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_ops_v1_router.get("/ops/automation/system-health", response_model=ScanApiV1Envelope)
def v1_ops_automation_system_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None, ge=1),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = get_ops_system_health(session, owner_user_id=owner_user_id)
    return wrap_object(body, owner_user_id=owner_user_id or int(current_user.id), checksum=body.latest_snapshot_checksum)
