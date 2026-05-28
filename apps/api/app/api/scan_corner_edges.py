"""P40-08 `/api/v1/scan-corner-edges/*` layered routes with deterministic envelopes."""

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
from app.schemas.scan_corner_edges import ScanCornerEdgeRunCreate
from app.services.ops_admin import ensure_ops_admin_access
from app.services.scan_corner_edges import (
    get_scan_corner_edge_artifact_owner,
    get_scan_corner_edge_run_owner,
    list_scan_corner_edge_evidence_owner,
    list_scan_corner_edge_failures_ops,
    list_scan_corner_edge_issues_ops,
    list_scan_corner_edge_issues_owner,
    list_scan_corner_edge_runs_ops,
    list_scan_corner_edge_runs_owner,
    run_scan_corner_edge_detection,
)

scan_corner_edges_v1_router = APIRouter(prefix="/api/v1", tags=["Scan Corner Edges API v1 (P40)"])


def _is_scan_corner_edges_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/scan-corner-edges") or path.startswith("/api/v1/ops/scan-corner-edges")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_scan_corner_edges_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _scan_corner_edges_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_scan_corner_edges_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}},
        )

    @app.exception_handler(RequestValidationError)
    async def _scan_corner_edges_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not _is_scan_corner_edges_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(scan_corner_edges_v1_router)


@scan_corner_edges_v1_router.post("/scan-corner-edges/run", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_owner_run_scan_corner_edges(
    payload: ScanCornerEdgeRunCreate,
    response: Response,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = run_scan_corner_edge_detection(session, settings, owner_user_id=int(current_user.id), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.corner_edge_checksum)


@scan_corner_edges_v1_router.get("/scan-corner-edges/runs", response_model=ScanApiV1Envelope)
def v1_owner_list_scan_corner_edge_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    scan_image_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_scan_corner_edge_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        scan_image_id=scan_image_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@scan_corner_edges_v1_router.get("/scan-corner-edges/runs/{run_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_corner_edge_run(
    run_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_scan_corner_edge_run_owner(session, settings, owner_user_id=int(current_user.id), run_id=run_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.corner_edge_checksum)


@scan_corner_edges_v1_router.get("/scan-corner-edges/evidence", response_model=ScanApiV1Envelope)
def v1_owner_list_scan_corner_edge_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    scan_image_id: int | None = Query(default=None),
    run_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_scan_corner_edge_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        scan_image_id=scan_image_id,
        corner_edge_run_id=run_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@scan_corner_edges_v1_router.get("/scan-corner-edges/issues", response_model=ScanApiV1Envelope)
def v1_owner_list_scan_corner_edge_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    run_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_scan_corner_edge_issues_owner(
        session,
        owner_user_id=int(current_user.id),
        corner_edge_run_id=run_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@scan_corner_edges_v1_router.get("/scan-corner-edges/artifacts/{artifact_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_corner_edge_artifact(
    artifact_id: int,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_scan_corner_edge_artifact_owner(session, settings, owner_user_id=int(current_user.id), artifact_id=artifact_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.artifact_checksum)


@scan_corner_edges_v1_router.get("/ops/scan-corner-edges/runs", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_corner_edge_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    scan_image_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_corner_edge_runs_ops(
        session,
        owner_user_id=owner_user_id,
        scan_image_id=scan_image_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@scan_corner_edges_v1_router.get("/ops/scan-corner-edges/issues", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_corner_edge_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_corner_edge_issues_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@scan_corner_edges_v1_router.get("/ops/scan-corner-edges/failures", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_corner_edge_failures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    body = list_scan_corner_edge_failures_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_user_id)
