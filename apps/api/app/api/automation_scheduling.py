"""P41-03 `/api/v1/automation/*` scheduling and trigger orchestration routes."""

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
from app.schemas.automation_scheduling import AutomationScheduleCreate, AutomationTriggerCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.automation_scheduling import (
    create_schedule,
    create_trigger,
    execute_workflow,
    get_automation_schedule_owner,
    get_automation_workflow_owner,
    list_automation_schedules_ops,
    list_automation_schedules_owner,
    list_automation_triggers_ops,
    list_automation_triggers_owner,
    list_automation_workflow_executions_owner,
    list_automation_workflow_history_owner,
    list_automation_workflow_issues_ops,
    list_automation_workflows_ops,
    list_automation_workflows_owner,
    process_due_schedules,
    process_triggers,
)
from app.services.ops_admin import ensure_ops_admin_access

automation_scheduling_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Scheduling API v1 (P41)"])


def _is_automation_scheduling_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation/schedules") or path.startswith("/api/v1/automation/triggers") or path.startswith("/api/v1/automation/workflows") or path.startswith("/api/v1/ops/automation/")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_scheduling_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_scheduling_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_scheduling_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_scheduling_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_scheduling_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_scheduling_v1_router)


@automation_scheduling_v1_router.post("/automation/schedules", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_owner_create_automation_schedule(
    payload: AutomationScheduleCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_schedule(session, owner_user_id=int(current_user.id), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.schedule_checksum)


@automation_scheduling_v1_router.get("/automation/schedules", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_schedules(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_schedules_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_scheduling_v1_router.get("/automation/schedules/{schedule_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_schedule(
    schedule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_schedule_owner(session, owner_user_id=int(current_user.id), schedule_id=schedule_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.schedule_checksum)


@automation_scheduling_v1_router.post("/automation/triggers", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_owner_create_automation_trigger(
    payload: AutomationTriggerCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_trigger(session, owner_user_id=int(current_user.id), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.trigger_checksum)


@automation_scheduling_v1_router.get("/automation/triggers", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_triggers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_triggers_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_scheduling_v1_router.get("/automation/workflows", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_workflows(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_workflows_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_scheduling_v1_router.get("/automation/workflows/{workflow_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_workflow(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_automation_workflow_owner(session, owner_user_id=int(current_user.id), workflow_id=workflow_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.workflow_key)


@automation_scheduling_v1_router.get("/automation/workflows/{workflow_id}/executions", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_workflow_executions(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_workflow_executions_owner(session, owner_user_id=int(current_user.id), workflow_id=workflow_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_scheduling_v1_router.get("/automation/workflows/{workflow_id}/history", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_workflow_history(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_workflow_history_owner(session, owner_user_id=int(current_user.id), workflow_id=workflow_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_scheduling_v1_router.post("/ops/automation/process-schedules", response_model=ScanApiV1Envelope)
def v1_ops_process_due_schedules(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = process_due_schedules(session, settings)
    return wrap_standard_list(body, owner_user_id=None)


@automation_scheduling_v1_router.post("/ops/automation/process-triggers", response_model=ScanApiV1Envelope)
def v1_ops_process_triggers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = process_triggers(session, settings)
    return wrap_standard_list(body, owner_user_id=None)


@automation_scheduling_v1_router.post("/ops/automation/workflows/{workflow_id}/execute", response_model=ScanApiV1Envelope)
def v1_ops_execute_workflow(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = execute_workflow(session, settings, workflow_id=workflow_id)
    return wrap_object(body, owner_user_id=None, snapshot_id=body.id, checksum=body.execution_checksum)


@automation_scheduling_v1_router.get("/ops/automation/schedules", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_schedules(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_schedules_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_scheduling_v1_router.get("/ops/automation/triggers", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_triggers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_triggers_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)


@automation_scheduling_v1_router.get("/ops/automation/workflows", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_workflows(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_workflows_ops(session, limit=limit, offset=offset, blocked_only=False)
    return wrap_standard_list(body, owner_user_id=None)


@automation_scheduling_v1_router.get("/ops/automation/workflows/blocked", response_model=ScanApiV1Envelope)
def v1_ops_list_blocked_automation_workflows(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_workflows_ops(session, limit=limit, offset=offset, blocked_only=True)
    return wrap_standard_list(body, owner_user_id=None)


@automation_scheduling_v1_router.get("/ops/automation/workflows/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_workflow_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_workflow_issues_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=None)
