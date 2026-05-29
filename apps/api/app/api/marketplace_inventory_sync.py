"""P43-03 `/api/v1/organizations/*/marketplace-sync` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_inventory_sync import (
    MarketplaceInventoryReconcileRequest,
    MarketplaceInventorySyncRunRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_inventory_sync_service import (
    get_inventory_sync_summary,
    list_inventory_conflicts,
    list_inventory_states,
    list_inventory_sync_runs,
    process_inventory_sync,
    reconcile_marketplace_inventory,
)

marketplace_inventory_sync_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Inventory Sync API v1 (P43-03)"])


def attach_marketplace_inventory_sync_layer(app: FastAPI) -> None:
    app.include_router(marketplace_inventory_sync_v1_router)


@marketplace_inventory_sync_v1_router.get("/organizations/{organization_id}/marketplace-sync", response_model=ScanApiV1Envelope)
def v1_get_marketplace_sync_summary(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_inventory_sync_summary(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_inventory_sync_v1_router.get("/organizations/{organization_id}/marketplace-sync/runs", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_runs(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    marketplace_account_id: int | None = Query(default=None, gt=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_inventory_sync_runs(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        marketplace_account_id=marketplace_account_id,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_inventory_sync_v1_router.get("/organizations/{organization_id}/marketplace-sync/conflicts", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_conflicts(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_inventory_conflicts(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_inventory_sync_v1_router.get("/organizations/{organization_id}/marketplace-sync/states", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_states(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    marketplace_account_id: int | None = Query(default=None, gt=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_inventory_states(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        marketplace_account_id=marketplace_account_id,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_inventory_sync_v1_router.post(
    "/organizations/{organization_id}/marketplace-sync/run",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_marketplace_sync(
    organization_id: int,
    payload: MarketplaceInventorySyncRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = process_inventory_sync(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_inventory_sync_v1_router.post(
    "/organizations/{organization_id}/marketplace-sync/reconcile",
    response_model=ScanApiV1Envelope,
)
def v1_reconcile_marketplace_sync(
    organization_id: int,
    payload: MarketplaceInventoryReconcileRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = reconcile_marketplace_inventory(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
