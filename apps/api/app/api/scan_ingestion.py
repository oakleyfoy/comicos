"""P40-01 `/api/v1/scan-ingestion/*` layered routes with deterministic envelopes."""

from __future__ import annotations

from typing import Any, Annotated

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.exceptions import RequestValidationError
from sqlmodel import Session
from starlette.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.scan_ingestion import ScanBatchCreatePayload, ScanBatchUploadPayload
from app.services.ops_admin import ensure_ops_admin_access
from app.services.scan_ingestion import (
    get_scan_image_owner,
    get_scan_ingestion_batch_owner,
    get_scan_upload_session_owner,
    list_scan_ingestion_batches_ops,
    list_scan_ingestion_batches_owner,
    list_scan_ingestion_failures_ops,
    register_scan_batch,
    register_uploaded_scan_batch,
)

scan_ingestion_v1_router = APIRouter(prefix="/api/v1", tags=["Scan Ingestion API v1 (P40)"])


def _is_scan_v1_path(path: str) -> bool:
    return path.startswith("/api/v1/scan-ingestion") or path.startswith("/api/v1/scan-images") or path.startswith(
        "/api/v1/scan-upload-sessions"
    ) or path.startswith("/api/v1/ops/scan-ingestion")


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_scan_ingestion_layer(app: FastAPI) -> None:
    from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
    from fastapi.exception_handlers import request_validation_exception_handler as default_request_validation_exception_handler

    @app.exception_handler(HTTPException)
    async def _scan_ingestion_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not _is_scan_v1_path(request.url.path):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}},
        )

    @app.exception_handler(RequestValidationError)
    async def _scan_ingestion_validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if not _is_scan_v1_path(request.url.path):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}},
        )

    app.include_router(scan_ingestion_v1_router)


@scan_ingestion_v1_router.post(
    "/scan-ingestion/upload",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
async def v1_owner_upload_scan_batch(
    response: Response,
    payload_json: Annotated[str, Form(alias="payload")],
    files: Annotated[list[UploadFile], File()],
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        payload = ScanBatchUploadPayload.model_validate_json(payload_json)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="payload must be JSON matching ScanBatchUploadPayload") from exc
    body, created = await register_uploaded_scan_batch(
        session,
        settings,
        owner_user_id=int(current_user.id),
        payload=payload,
        files=files,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.ingestion_checksum)


@scan_ingestion_v1_router.post(
    "/scan-ingestion/batch",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_owner_create_scan_batch(
    payload: ScanBatchCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = register_scan_batch(session, owner_user_id=int(current_user.id), payload=payload)
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.ingestion_checksum)


@scan_ingestion_v1_router.get("/scan-ingestion/batches", response_model=ScanApiV1Envelope)
def v1_owner_list_scan_batches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = list_scan_ingestion_batches_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(rows, owner_user_id=int(current_user.id))


@scan_ingestion_v1_router.get("/scan-ingestion/batches/{batch_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_batch(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = get_scan_ingestion_batch_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.id, checksum=row.ingestion_checksum)


@scan_ingestion_v1_router.get("/scan-images/{scan_image_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_image(
    scan_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = get_scan_image_owner(session, owner_user_id=int(current_user.id), scan_image_id=scan_image_id)
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.id, checksum=row.sha256_checksum)


@scan_ingestion_v1_router.get("/scan-upload-sessions/{upload_session_id}", response_model=ScanApiV1Envelope)
def v1_owner_get_scan_upload_session(
    upload_session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = get_scan_upload_session_owner(session, owner_user_id=int(current_user.id), upload_session_id=upload_session_id)
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.id, checksum=row.session_checksum)


@scan_ingestion_v1_router.get("/ops/scan-ingestion/batches", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_batches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    from app.services.ops_ingestion_safe_get import safe_list_scan_ingestion_batches_ops

    rows = safe_list_scan_ingestion_batches_ops(
        session, owner_user_id=owner_user_id, limit=limit, offset=offset
    )
    return wrap_standard_list(rows, owner_user_id=owner_user_id)


@scan_ingestion_v1_router.get("/ops/scan-ingestion/failures", response_model=ScanApiV1Envelope)
def v1_ops_list_scan_failures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    from app.services.ops_ingestion_safe_get import safe_list_scan_ingestion_failures_ops

    rows = safe_list_scan_ingestion_failures_ops(
        session, owner_user_id=owner_user_id, limit=limit, offset=offset
    )
    return wrap_standard_list(rows, owner_user_id=owner_user_id)
