"""P41-02 `/api/v1/automation/workers*` deterministic worker runtime routes."""

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
from app.schemas.automation_workers import (
    AutomationWorkerExecutionComplete,
    AutomationWorkerExecutionFail,
    AutomationWorkerExecutionStart,
    AutomationWorkerHeartbeatCreate,
    AutomationWorkerLeaseAcquire,
    AutomationWorkerLeaseRenew,
    AutomationWorkerRegister,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.automation_workers import (
    acquire_job_lease,
    complete_job_execution,
    fail_job_execution,
    get_automation_worker_ops,
    get_automation_worker_owner,
    list_automation_worker_executions_owner,
    list_automation_worker_history_owner,
    list_automation_worker_issues_ops,
    list_automation_worker_issues_owner,
    list_automation_workers_ops,
    list_automation_workers_owner,
    record_worker_heartbeat,
    register_worker,
    release_expired_leases,
    renew_worker_lease,
    start_job_execution,
)
from app.services.ops_admin import ensure_ops_admin_access

automation_workers_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Workers API v1 (P41)"])


def _is_automation_workers_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation/workers") or path.startswith("/api/v1/ops/automation/workers")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_workers_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_workers_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_workers_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_workers_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_workers_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_workers_v1_router)


@automation_workers_v1_router.get("/automation/workers", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_workers(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_workers_owner(session, settings, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_workers_v1_router.get("/automation/workers/{worker_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_worker(
    worker_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_worker_owner(session, settings, owner_user_id=int(current_user.id), worker_id=worker_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.worker_key)


@automation_workers_v1_router.get("/automation/workers/{worker_id}/executions", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_worker_executions(
    worker_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_worker_executions_owner(session, owner_user_id=int(current_user.id), worker_id=worker_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_workers_v1_router.get("/automation/workers/{worker_id}/history", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_worker_history(
    worker_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_worker_history_owner(session, owner_user_id=int(current_user.id), worker_id=worker_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_workers_v1_router.get("/automation/workers/{worker_id}/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_worker_issues(
    worker_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_worker_issues_owner(session, owner_user_id=int(current_user.id), worker_id=worker_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_workers_v1_router.post("/ops/automation/workers/register", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_register_automation_worker(
    payload: AutomationWorkerRegister,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body, created = register_worker(session, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.worker_key)


@automation_workers_v1_router.post("/ops/automation/workers/{worker_id}/heartbeat", response_model=ScanApiV1Envelope)
def v1_ops_record_worker_heartbeat(
    worker_id: int,
    payload: AutomationWorkerHeartbeatCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = record_worker_heartbeat(session, worker_id=worker_id, payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id)


@automation_workers_v1_router.post("/ops/automation/workers/{worker_id}/lease", response_model=ScanApiV1Envelope)
def v1_ops_acquire_worker_lease(
    worker_id: int,
    payload: AutomationWorkerLeaseAcquire,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = acquire_job_lease(session, worker_id=worker_id, payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.reservation_token)


@automation_workers_v1_router.post("/ops/automation/workers/{worker_id}/lease/renew", response_model=ScanApiV1Envelope)
def v1_ops_renew_worker_lease(
    worker_id: int,
    payload: AutomationWorkerLeaseRenew,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = renew_worker_lease(session, worker_id=worker_id, payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.reservation_token)


@automation_workers_v1_router.post("/ops/automation/workers/{worker_id}/execution/start", response_model=ScanApiV1Envelope)
def v1_ops_start_worker_execution(
    worker_id: int,
    payload: AutomationWorkerExecutionStart,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = start_job_execution(session, settings, worker_id=worker_id, payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.execution_checksum)


@automation_workers_v1_router.post("/ops/automation/workers/{worker_id}/execution/complete", response_model=ScanApiV1Envelope)
def v1_ops_complete_worker_execution(
    worker_id: int,
    payload: AutomationWorkerExecutionComplete,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = complete_job_execution(session, settings, worker_id=worker_id, payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.execution_checksum)


@automation_workers_v1_router.post("/ops/automation/workers/{worker_id}/execution/fail", response_model=ScanApiV1Envelope)
def v1_ops_fail_worker_execution(
    worker_id: int,
    payload: AutomationWorkerExecutionFail,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = fail_job_execution(session, settings, worker_id=worker_id, payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.execution_checksum)


@automation_workers_v1_router.post("/ops/automation/workers/release-expired", response_model=ScanApiV1Envelope)
def v1_ops_release_expired_worker_leases(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = release_expired_leases(session)
    return wrap_standard_list(body, owner_user_id=None)


@automation_workers_v1_router.get("/ops/automation/workers", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_workers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_workers_ops(session, settings, stale_only=False, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_workers_v1_router.get("/ops/automation/workers/stale", response_model=ScanApiV1Envelope)
def v1_ops_list_stale_automation_workers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_workers_ops(session, settings, stale_only=True, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_workers_v1_router.get("/ops/automation/workers/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_worker_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_worker_issues_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)
