"""P41-05 `/api/v1/automation/batch*` batch and maintenance routes."""

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
from app.schemas.automation_batch import AutomationBatchRunCreate, AutomationMaintenanceRunCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.automation_batch import (
    create_batch_run,
    execute_batch_run,
    execute_maintenance_job,
    get_automation_batch_run_ops,
    get_automation_batch_run_owner,
    list_automation_batch_chunks_owner,
    list_automation_batch_issues_ops,
    list_automation_batch_issues_owner,
    list_automation_batch_runs_ops,
    list_automation_batch_runs_owner,
    list_automation_maintenance_jobs_ops,
    list_automation_maintenance_jobs_owner,
    list_automation_maintenance_results_owner,
)
from app.services.ops_admin import ensure_ops_admin_access

automation_batch_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Batch API v1 (P41)"])


def _is_automation_batch_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation/batch") or path.startswith("/api/v1/automation/maintenance") or path.startswith("/api/v1/ops/automation/")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_batch_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_batch_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_batch_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_batch_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_batch_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_batch_v1_router)


@automation_batch_v1_router.get("/automation/batch/runs", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_batch_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_batch_runs_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_batch_v1_router.get("/automation/batch/runs/{batch_run_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_batch_run(
    batch_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_batch_run_owner(session, owner_user_id=int(current_user.id), batch_run_id=batch_run_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.batch_checksum)


@automation_batch_v1_router.get("/automation/batch/runs/{batch_run_id}/chunks", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_batch_chunks(
    batch_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_batch_chunks_owner(session, owner_user_id=int(current_user.id), batch_run_id=batch_run_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_batch_v1_router.get("/automation/maintenance/jobs", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_maintenance_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_maintenance_jobs_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_batch_v1_router.get("/automation/maintenance/results", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_maintenance_results(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_maintenance_results_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_batch_v1_router.get("/automation/batch/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_batch_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_batch_issues_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_batch_v1_router.post("/ops/automation/batch/create", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_create_batch_run(
    payload: AutomationBatchRunCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body, created = create_batch_run(session, settings, owner_user_id=int(current_user.id or 0), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.batch_checksum)


@automation_batch_v1_router.post("/ops/automation/batch/{batch_run_id}/execute", response_model=ScanApiV1Envelope)
def v1_ops_execute_batch_run(
    batch_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = execute_batch_run(session, settings, batch_run_id=batch_run_id)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.batch_checksum)


@automation_batch_v1_router.post("/ops/automation/maintenance/run", response_model=ScanApiV1Envelope)
def v1_ops_execute_maintenance_job(
    payload: AutomationMaintenanceRunCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = execute_maintenance_job(session, settings, owner_user_id=int(current_user.id or 0), payload=payload)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.maintenance_checksum)


@automation_batch_v1_router.get("/ops/automation/batch/runs", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_batch_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_batch_runs_ops(session, limit=limit, offset=offset, failed_only=False)
    return wrap_standard_list(body, owner_user_id=None)


@automation_batch_v1_router.get("/ops/automation/batch/failed", response_model=ScanApiV1Envelope)
def v1_ops_list_failed_automation_batch_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_batch_runs_ops(session, limit=limit, offset=offset, failed_only=True)
    return wrap_standard_list(body, owner_user_id=None)


@automation_batch_v1_router.get("/ops/automation/maintenance/jobs", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_maintenance_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_maintenance_jobs_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_batch_v1_router.get("/ops/automation/maintenance/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_maintenance_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_batch_issues_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_batch_v1_router.get("/ops/automation/storage-audit", response_model=ScanApiV1Envelope)
def v1_ops_list_storage_audits(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_maintenance_jobs_ops(session, limit=limit, offset=offset, maintenance_types={"STORAGE_AUDIT"})
    return wrap_standard_list(body, owner_user_id=None)


@automation_batch_v1_router.get("/ops/automation/integrity-audit", response_model=ScanApiV1Envelope)
def v1_ops_list_integrity_audits(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_maintenance_jobs_ops(
        session,
        limit=limit,
        offset=offset,
        maintenance_types={"CHECKSUM_AUDIT", "LINEAGE_AUDIT", "QUEUE_INTEGRITY_CHECK", "REPLAY_AUDIT"},
    )
    return wrap_standard_list(body, owner_user_id=None)
