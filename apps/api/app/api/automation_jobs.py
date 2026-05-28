"""P41-01 `/api/v1/automation/*` deterministic queue foundation routes."""

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
from app.schemas.automation_jobs import (
    AutomationJobAttemptListResponse,
    AutomationJobCreate,
    AutomationJobHistoryListResponse,
    AutomationJobIssueListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.automation_jobs import (
    create_automation_job,
    get_automation_job_artifact_owner,
    get_automation_job_owner,
    get_automation_queue_health_ops,
    list_automation_issues_ops,
    list_automation_job_attempts_owner,
    list_automation_job_history_owner,
    list_automation_job_issues_owner,
    list_automation_jobs_dead_letter_ops,
    list_automation_jobs_failed_ops,
    list_automation_jobs_ops,
    list_automation_jobs_owner,
    list_automation_queues_ops,
)
from app.services.ops_admin import ensure_ops_admin_access

automation_jobs_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Jobs API v1 (P41)"])


def _is_automation_jobs_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation") or path.startswith("/api/v1/ops/automation")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_jobs_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_jobs_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_jobs_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_jobs_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_jobs_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_jobs_v1_router)


@automation_jobs_v1_router.post("/automation/jobs", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_owner_create_automation_job(
    payload: AutomationJobCreate,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_automation_job(session, settings, owner_user_id=int(current_user.id), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.job_checksum)


@automation_jobs_v1_router.get("/automation/jobs", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    queue_key: str | None = Query(default=None),
    job_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_jobs_owner(session, owner_user_id=int(current_user.id), queue_key=queue_key, job_status=job_status, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_jobs_v1_router.get("/automation/jobs/{job_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_job(
    job_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_job_owner(session, settings, owner_user_id=int(current_user.id), job_id=job_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.job_checksum)


@automation_jobs_v1_router.get("/automation/jobs/{job_id}/attempts", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_job_attempts(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_automation_job_attempts_owner(session, owner_user_id=int(current_user.id), job_id=job_id)
    body = AutomationJobAttemptListResponse(items=items, total_items=len(items), limit=len(items) or 1, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_jobs_v1_router.get("/automation/jobs/{job_id}/history", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_job_history(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_automation_job_history_owner(session, owner_user_id=int(current_user.id), job_id=job_id)
    body = AutomationJobHistoryListResponse(items=items, total_items=len(items), limit=len(items) or 1, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_jobs_v1_router.get("/automation/jobs/{job_id}/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_job_issues(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_automation_job_issues_owner(session, owner_user_id=int(current_user.id), job_id=job_id)
    severity_counts: dict[str, int] = {}
    for row in items:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    body = AutomationJobIssueListResponse(items=items, total_items=len(items), limit=len(items) or 1, offset=0, severity_counts=severity_counts)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_jobs_v1_router.get("/automation/jobs/{job_id}/artifacts/{artifact_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_job_artifact(
    job_id: int,
    artifact_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_job_artifact_owner(session, settings, owner_user_id=int(current_user.id), job_id=job_id, artifact_id=artifact_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.artifact_checksum)


@automation_jobs_v1_router.get("/ops/automation/queues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_queues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_queues_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_jobs_v1_router.get("/ops/automation/jobs", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    organization_id: int | None = Query(default=None),
    queue_key: str | None = Query(default=None),
    job_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_jobs_ops(
        session,
        owner_user_id=owner_user_id,
        organization_id=organization_id,
        queue_key=queue_key,
        job_status=job_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@automation_jobs_v1_router.get("/ops/automation/jobs/failed", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_jobs_failed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_jobs_failed_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@automation_jobs_v1_router.get("/ops/automation/jobs/dead-letter", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_jobs_dead_letter(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_jobs_dead_letter_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@automation_jobs_v1_router.get("/ops/automation/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    items = list_automation_issues_ops(session, limit=limit, offset=offset)
    severity_counts: dict[str, int] = {}
    for row in items:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    body = AutomationJobIssueListResponse(items=items, total_items=len(items), limit=limit, offset=offset, severity_counts=severity_counts)
    return wrap_standard_list(body, owner_user_id=None)


@automation_jobs_v1_router.get("/ops/automation/queue-health", response_model=ScanApiV1Envelope)
def v1_ops_get_automation_queue_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = get_automation_queue_health_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)
