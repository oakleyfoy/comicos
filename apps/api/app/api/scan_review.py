"""P40-14 `/api/v1/scan-review/*` layered routes with deterministic envelopes."""

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
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.scan_review import (
    ScanReviewDecisionCreate,
    ScanReviewEvidenceActionCreate,
    ScanReviewNoteCreate,
    ScanReviewSessionCreate,
)
from app.services.ops_admin import ensure_ops_admin_access
from app.services.scan_review import (
    complete_review_session,
    create_scan_review_session,
    get_scan_review_artifact_owner,
    get_scan_review_session_owner,
    list_scan_review_blocked_ops,
    list_scan_review_issues_ops,
    list_scan_review_issues_owner,
    list_scan_review_rescans_ops,
    list_scan_review_sessions_ops,
    list_scan_review_sessions_owner,
    record_evidence_action,
    record_review_decision,
    record_review_note,
)

scan_review_v1_router = APIRouter(prefix="/api/v1", tags=["Scan Review API v1 (P40)"])


def _is_scan_review_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/scan-review") or path.startswith("/api/v1/ops/scan-review")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_scan_review_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _scan_review_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_scan_review_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}})

    @app.exception_handler(RequestValidationError)
    async def _scan_review_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_scan_review_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(scan_review_v1_router)


@scan_review_v1_router.post("/scan-review/sessions", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_owner_create_scan_review_session(
    payload: ScanReviewSessionCreate,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_scan_review_session(
        session,
        settings,
        owner_user_id=int(current_user.id),
        reviewer_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.review_checksum)


@scan_review_v1_router.get("/scan-review/sessions", response_model=ScanApiV1Envelope)
def v1_owner_list_scan_review_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    scan_image_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_scan_review_sessions_owner(session, owner_user_id=int(current_user.id), scan_image_id=scan_image_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@scan_review_v1_router.get("/scan-review/sessions/{review_session_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_review_session(
    review_session_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_scan_review_session_owner(session, settings, owner_user_id=int(current_user.id), review_session_id=review_session_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.review_checksum)


@scan_review_v1_router.post("/scan-review/sessions/{review_session_id}/decisions", response_model=ScanApiV1Envelope)
def v1_owner_record_scan_review_decision(
    review_session_id: int,
    payload: ScanReviewDecisionCreate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = record_review_decision(session, settings, owner_user_id=int(current_user.id), review_session_id=review_session_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.review_checksum)


@scan_review_v1_router.post("/scan-review/sessions/{review_session_id}/notes", response_model=ScanApiV1Envelope)
def v1_owner_record_scan_review_note(
    review_session_id: int,
    payload: ScanReviewNoteCreate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = record_review_note(session, settings, owner_user_id=int(current_user.id), review_session_id=review_session_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.review_checksum)


@scan_review_v1_router.post("/scan-review/sessions/{review_session_id}/evidence-actions", response_model=ScanApiV1Envelope)
def v1_owner_record_scan_review_evidence_action(
    review_session_id: int,
    payload: ScanReviewEvidenceActionCreate,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = record_evidence_action(session, settings, owner_user_id=int(current_user.id), review_session_id=review_session_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.review_checksum)


@scan_review_v1_router.post("/scan-review/sessions/{review_session_id}/complete", response_model=ScanApiV1Envelope)
def v1_owner_complete_scan_review_session(
    review_session_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_review_session(session, settings, owner_user_id=int(current_user.id), review_session_id=review_session_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.review_checksum)


@scan_review_v1_router.get("/scan-review/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_scan_review_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    review_session_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_scan_review_issues_owner(
        session,
        owner_user_id=int(current_user.id),
        review_session_id=review_session_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@scan_review_v1_router.get("/scan-review/artifacts/{artifact_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_review_artifact(
    artifact_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_scan_review_artifact_owner(session, settings, owner_user_id=int(current_user.id), artifact_id=artifact_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.artifact_checksum)


@scan_review_v1_router.get("/ops/scan-review/sessions", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_review_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    scan_image_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_review_sessions_ops(session, owner_user_id=owner_user_id, scan_image_id=scan_image_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@scan_review_v1_router.get("/ops/scan-review/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_review_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_review_issues_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@scan_review_v1_router.get("/ops/scan-review/blocked", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_review_blocked(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_review_blocked_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@scan_review_v1_router.get("/ops/scan-review/rescans", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_review_rescans(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_review_rescans_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)

