"""P44-01 `/api/v1/organizations/*/mobile` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, Response, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.mobile_foundation import (
    MobileDeviceRegisterRequest,
    MobileDeviceUpdateRequest,
    MobileSessionCreateRequest,
    OfflineSyncContractCreateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.mobile_foundation_service import (
    build_mobile_foundation_dashboard,
    create_mobile_session,
    create_offline_sync_contract,
    list_mobile_devices,
    list_mobile_sessions,
    list_offline_sync_contracts,
    register_mobile_device,
    update_mobile_device,
)

mobile_foundation_v1_router = APIRouter(prefix="/api/v1", tags=["Mobile Foundation API v1 (P44-01)"])


def attach_mobile_foundation_layer(app: FastAPI) -> None:
    app.include_router(mobile_foundation_v1_router)


@mobile_foundation_v1_router.get("/organizations/{organization_id}/mobile", response_model=ScanApiV1Envelope)
def v1_get_mobile_foundation_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_mobile_foundation_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@mobile_foundation_v1_router.get("/organizations/{organization_id}/mobile/devices", response_model=ScanApiV1Envelope)
def v1_list_mobile_devices(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_mobile_devices(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_foundation_v1_router.post(
    "/organizations/{organization_id}/mobile/devices",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_register_mobile_device(
    organization_id: int,
    payload: MobileDeviceRegisterRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = register_mobile_device(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_foundation_v1_router.patch(
    "/organizations/{organization_id}/mobile/devices/{device_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_mobile_device(
    organization_id: int,
    device_id: int,
    payload: MobileDeviceUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_mobile_device(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        device_id=device_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_foundation_v1_router.get("/organizations/{organization_id}/mobile/sessions", response_model=ScanApiV1Envelope)
def v1_list_mobile_sessions(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_mobile_sessions(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_foundation_v1_router.post(
    "/organizations/{organization_id}/mobile/sessions",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_mobile_session(
    organization_id: int,
    payload: MobileSessionCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_mobile_session(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@mobile_foundation_v1_router.get("/organizations/{organization_id}/mobile/contracts", response_model=ScanApiV1Envelope)
def v1_list_offline_sync_contracts(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_offline_sync_contracts(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@mobile_foundation_v1_router.post(
    "/organizations/{organization_id}/mobile/contracts",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_offline_sync_contract(
    organization_id: int,
    payload: OfflineSyncContractCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_offline_sync_contract(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
