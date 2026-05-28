"""P41-08 `/api/v1/automation/rules*` rules engine routes."""

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
from app.schemas.automation_rules import (
    AutomationRuleCreate,
    AutomationRuleEvaluateCreate,
    AutomationRuleVersionCreate,
    AutomationSystemRuleEvaluateCreate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.automation_rules import (
    create_rule,
    create_rule_version,
    evaluate_rule,
    evaluate_system_rules,
    get_automation_rule_owner,
    list_automation_rule_actions_owner,
    list_automation_rule_drift_ops,
    list_automation_rule_evaluations_owner,
    list_automation_rule_failures_ops,
    list_automation_rule_issues_ops,
    list_automation_rule_issues_owner,
    list_automation_rule_versions_owner,
    list_automation_rules_ops,
    list_automation_rules_owner,
)
from app.services.ops_admin import ensure_ops_admin_access

automation_rules_v1_router = APIRouter(prefix="/api/v1", tags=["Automation Rules API v1 (P41)"])


def _is_automation_rules_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/automation/rules") or path.startswith("/api/v1/ops/automation/rules")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_automation_rules_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _automation_rules_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_automation_rules_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _automation_rules_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_automation_rules_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(automation_rules_v1_router)


@automation_rules_v1_router.get("/automation/rules", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_rules(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_rules_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_rules_v1_router.get("/automation/rules/{rule_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_automation_rule(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = get_automation_rule_owner(session, owner_user_id=int(current_user.id), rule_id=rule_id)
    checksum = row.current_version.version_checksum if row.current_version is not None else None
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.id, checksum=checksum)


@automation_rules_v1_router.get("/automation/rules/{rule_id}/versions", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_rule_versions(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_rule_versions_owner(session, owner_user_id=int(current_user.id), rule_id=rule_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_rules_v1_router.get("/automation/rules/{rule_id}/evaluations", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_rule_evaluations(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_rule_evaluations_owner(session, owner_user_id=int(current_user.id), rule_id=rule_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_rules_v1_router.get("/automation/rules/{rule_id}/actions", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_rule_actions(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_rule_actions_owner(session, owner_user_id=int(current_user.id), rule_id=rule_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_rules_v1_router.get("/automation/rules/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_automation_rule_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_automation_rule_issues_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@automation_rules_v1_router.post("/ops/automation/rules/create", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_create_automation_rule(
    payload: AutomationRuleCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row, created = create_rule(session, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    checksum = row.current_version.version_checksum if row.current_version is not None else None
    return wrap_object(row, owner_user_id=payload.owner_user_id, snapshot_id=row.id, checksum=checksum)


@automation_rules_v1_router.post("/ops/automation/rules/{rule_id}/version", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_create_automation_rule_version(
    rule_id: int,
    payload: AutomationRuleVersionCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row, created = create_rule_version(session, rule_id=rule_id, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(row, owner_user_id=int(current_user.id or 0), snapshot_id=row.id, checksum=row.version_checksum)


@automation_rules_v1_router.post("/ops/automation/rules/{rule_id}/evaluate", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_ops_evaluate_automation_rule(
    rule_id: int,
    payload: AutomationRuleEvaluateCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row, created = evaluate_rule(session, settings, rule_id=rule_id, payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(row, owner_user_id=int(current_user.id or 0), snapshot_id=row.id, checksum=row.evaluation_checksum)


@automation_rules_v1_router.post("/ops/automation/rules/evaluate-system", response_model=ScanApiV1Envelope)
def v1_ops_evaluate_system_rules(
    payload: AutomationSystemRuleEvaluateCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = evaluate_system_rules(session, settings, payload=payload)
    return wrap_standard_list(body, owner_user_id=payload.owner_user_id or int(current_user.id or 0))


@automation_rules_v1_router.get("/ops/automation/rules", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_rules(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_rules_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id or 0))


@automation_rules_v1_router.get("/ops/automation/rules/failures", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_rule_failures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_rule_failures_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id or 0))


@automation_rules_v1_router.get("/ops/automation/rules/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_rule_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_rule_issues_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id or 0))


@automation_rules_v1_router.get("/ops/automation/rules/drift", response_model=ScanApiV1Envelope)
def v1_ops_list_automation_rule_drift(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_automation_rule_drift_ops(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id or 0))
