"""P44-03 `/api/v1/organizations/*/mobile-scanning` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.mobile_scanning import IntakeStagingCreateRequest, IntakeStagingUpdateRequest, ScanCaptureRequest
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.mobile_scanning_service import (
    build_mobile_scanning_dashboard,
    capture_scan,
    create_staging_record,
    list_lookup_results,
    list_scans,
    list_staging_records,
    update_staging_record,
)

mobile_scanning_v1_router = APIRouter(prefix="/api/v1", tags=["Mobile Scanning API v1 (P44-03)"])


def attach_mobile_scanning_layer(app: FastAPI) -> None:
    app.include_router(mobile_scanning_v1_router)


@mobile_scanning_v1_router.get("/organizations/{organization_id}/mobile-scanning", response_model=ScanApiV1Envelope)
def v1_get_mobile_scanning_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_mobile_scanning_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@mobile_scanning_v1_router.get("/organizations/{organization_id}/mobile-scanning/scans", response_model=ScanApiV1Envelope)
def v1_list_scan_captures(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_scans(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_scanning_v1_router.get("/organizations/{organization_id}/mobile-scanning/staging", response_model=ScanApiV1Envelope)
def v1_list_intake_staging_records(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_staging_records(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_scanning_v1_router.get("/organizations/{organization_id}/mobile-scanning/lookups", response_model=ScanApiV1Envelope)
def v1_list_scan_lookup_results(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_lookup_results(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_scanning_v1_router.post(
    "/organizations/{organization_id}/mobile-scanning/capture",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_capture_scan(
    organization_id: int,
    payload: ScanCaptureRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = capture_scan(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.capture.id)


@mobile_scanning_v1_router.post(
    "/organizations/{organization_id}/mobile-scanning/staging",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_intake_staging_record(
    organization_id: int,
    payload: IntakeStagingCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_staging_record(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_scanning_v1_router.patch(
    "/organizations/{organization_id}/mobile-scanning/staging/{staging_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_intake_staging_record(
    organization_id: int,
    staging_id: int,
    payload: IntakeStagingUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_staging_record(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        staging_id=staging_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
