"""P43-04 `/api/v1/organizations/*/marketplace-orders` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_orders import MarketplaceOrderImportRequest, MarketplaceOrderReconcileRequest
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_order_service import (
    create_order_import,
    get_marketplace_order,
    list_marketplace_orders,
    list_marketplace_transactions,
    reconcile_marketplace_orders,
)

marketplace_orders_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Orders API v1 (P43-04)"])


def attach_marketplace_order_layer(app: FastAPI) -> None:
    app.include_router(marketplace_orders_v1_router)


@marketplace_orders_v1_router.get("/organizations/{organization_id}/marketplace-orders", response_model=ScanApiV1Envelope)
def v1_list_marketplace_orders(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_orders(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_orders_v1_router.get("/organizations/{organization_id}/marketplace-orders/{order_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_order(
    organization_id: int,
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace_order(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        order_id=order_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=order_id)


@marketplace_orders_v1_router.get("/organizations/{organization_id}/marketplace-transactions", response_model=ScanApiV1Envelope)
def v1_list_marketplace_transactions(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_transactions(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_orders_v1_router.post(
    "/organizations/{organization_id}/marketplace-orders/import",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_import_marketplace_order(
    organization_id: int,
    payload: MarketplaceOrderImportRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_order_import(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.order.id)


@marketplace_orders_v1_router.post(
    "/organizations/{organization_id}/marketplace-orders/reconcile",
    response_model=ScanApiV1Envelope,
)
def v1_reconcile_marketplace_orders(
    organization_id: int,
    payload: MarketplaceOrderReconcileRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = reconcile_marketplace_orders(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
