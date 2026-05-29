"""P44-02 `/api/v1/organizations/*/offline-inventory` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, Response, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.offline_inventory import (
    OfflineInventoryChangeRegisterRequest,
    OfflineInventoryRecordCreateRequest,
    OfflineSyncConflictUpdateRequest,
    OfflineSyncQueueCreateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.offline_inventory_service import (
    acknowledge_sync_conflict,
    build_offline_inventory_dashboard,
    create_offline_inventory_record,
    list_inventory_changes,
    list_sync_conflicts,
    list_sync_queue,
    queue_sync_operation,
    register_inventory_change,
)

offline_inventory_v1_router = APIRouter(prefix="/api/v1", tags=["Offline Inventory API v1 (P44-02)"])


def attach_offline_inventory_layer(app: FastAPI) -> None:
    app.include_router(offline_inventory_v1_router)


@offline_inventory_v1_router.get("/organizations/{organization_id}/offline-inventory", response_model=ScanApiV1Envelope)
def v1_get_offline_inventory_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_offline_inventory_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@offline_inventory_v1_router.get("/organizations/{organization_id}/offline-inventory/changes", response_model=ScanApiV1Envelope)
def v1_list_offline_inventory_changes(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_inventory_changes(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@offline_inventory_v1_router.get("/organizations/{organization_id}/offline-inventory/queue", response_model=ScanApiV1Envelope)
def v1_list_offline_sync_queue(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_sync_queue(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@offline_inventory_v1_router.get("/organizations/{organization_id}/offline-inventory/conflicts", response_model=ScanApiV1Envelope)
def v1_list_offline_sync_conflicts(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_sync_conflicts(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@offline_inventory_v1_router.post(
    "/organizations/{organization_id}/offline-inventory",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_offline_inventory_record(
    organization_id: int,
    payload: OfflineInventoryRecordCreateRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = create_offline_inventory_record(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@offline_inventory_v1_router.post(
    "/organizations/{organization_id}/offline-inventory/change",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_register_offline_inventory_change(
    organization_id: int,
    payload: OfflineInventoryChangeRegisterRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = register_inventory_change(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@offline_inventory_v1_router.post(
    "/organizations/{organization_id}/offline-inventory/queue",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_queue_offline_sync_operation(
    organization_id: int,
    payload: OfflineSyncQueueCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = queue_sync_operation(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@offline_inventory_v1_router.patch(
    "/organizations/{organization_id}/offline-inventory/conflicts/{conflict_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_offline_sync_conflict(
    organization_id: int,
    conflict_id: int,
    payload: OfflineSyncConflictUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = acknowledge_sync_conflict(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        conflict_id=conflict_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
