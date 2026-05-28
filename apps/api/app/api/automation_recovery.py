"""P41-04 `/api/v1/automation/recovery*` retry and recovery routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from sqlmodel import Session
from starlette.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.automation_recovery import AutomationRetryPolicyCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.automation_recovery import (
    create_retry_policy,
    get_automation_recovery_run_ops,
    get_automation_recovery_run_owner,
    list_automation_dead_letter_ops,
    list_automation_dead_letter_owner,
    list_automation_failure_events_ops,
    list_automation_failure_events_owner,
    list_automation_recovery_issues_ops,
    list_automation_recovery_issues_owner,
    list_automation_recovery_runs_ops,
    list_automation_recovery_runs_owner,
    recover_expired_execution,
    replay_failed_job,
    schedule_retry,
    transfer_to_dead_letter,
)
from app.services.ops_admin import ensure_ops_admin_access

automation_recovery_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Recovery API v1 (P41)"])


def _is_automation_recovery_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation/recovery") or path.startswith("/api/v1/automation/dead-letter") or path.startswith("/api/v1/automation/failures") or path.startswith("/api/v1/ops/automation/")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_recovery_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_recovery_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_recovery_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_recovery_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_recovery_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_recovery_v1_router)


@automation_recovery_v1_router.get("/automation/recovery/runs", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_recovery_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_recovery_runs_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_recovery_v1_router.get("/automation/recovery/runs/{run_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_recovery_run(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_recovery_run_owner(session, owner_user_id=int(current_user.id), run_id=run_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.recovery_checksum)


@automation_recovery_v1_router.get("/automation/dead-letter", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_dead_letter(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_dead_letter_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_recovery_v1_router.get("/automation/failures", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_failures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_failure_events_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_recovery_v1_router.get("/automation/recovery/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_recovery_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_recovery_issues_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_recovery_v1_router.post("/ops/automation/retry-policies", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_create_retry_policy(
    payload: AutomationRetryPolicyCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body, created = create_retry_policy(session, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.policy_checksum)


@automation_recovery_v1_router.post("/ops/automation/jobs/{job_id}/retry", response_model=ScanApiV1Envelope)
def v1_ops_schedule_retry(
    job_id: int,
    retry_policy_id: int = Body(embed=True),
    metadata_json: dict[str, Any] = Body(default_factory=dict),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = schedule_retry(session, settings, job_id=job_id, retry_policy_id=retry_policy_id, metadata_json=metadata_json)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.recovery_checksum)


@automation_recovery_v1_router.post("/ops/automation/jobs/{job_id}/dead-letter", response_model=ScanApiV1Envelope)
def v1_ops_transfer_dead_letter(
    job_id: int,
    dead_letter_reason: str = Body(embed=True),
    metadata_json: dict[str, Any] = Body(default_factory=dict),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = transfer_to_dead_letter(session, settings, job_id=job_id, dead_letter_reason=dead_letter_reason, metadata_json=metadata_json)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.recovery_checksum)


@automation_recovery_v1_router.post("/ops/automation/jobs/{job_id}/replay-recovery", response_model=ScanApiV1Envelope)
def v1_ops_replay_failed_job(
    job_id: int,
    metadata_json: dict[str, Any] = Body(default_factory=dict),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = replay_failed_job(session, settings, job_id=job_id, metadata_json=metadata_json)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.recovery_checksum)


@automation_recovery_v1_router.post("/ops/automation/executions/{execution_id}/recover", response_model=ScanApiV1Envelope)
def v1_ops_recover_expired_execution(
    execution_id: int,
    metadata_json: dict[str, Any] = Body(default_factory=dict),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = recover_expired_execution(session, settings, execution_id=execution_id, metadata_json=metadata_json)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.recovery_checksum)


@automation_recovery_v1_router.get("/ops/automation/recovery/runs", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_recovery_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_recovery_runs_ops(session, limit=limit, offset=offset, critical_only=False)
    return wrap_standard_list(body, owner_user_id=None)


@automation_recovery_v1_router.get("/ops/automation/dead-letter", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_dead_letter(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_dead_letter_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_recovery_v1_router.get("/ops/automation/failures", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_failures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_failure_events_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_recovery_v1_router.get("/ops/automation/recovery/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_recovery_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_recovery_issues_ops(session, limit=limit, offset=offset, critical_only=False)
    return wrap_standard_list(body, owner_user_id=None)


@automation_recovery_v1_router.get("/ops/automation/recovery/critical", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_recovery_critical(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_recovery_issues_ops(session, limit=limit, offset=offset, critical_only=True)
    return wrap_standard_list(body, owner_user_id=None)
