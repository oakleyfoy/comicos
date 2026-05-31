from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_sync import (
    MarketplaceInventoryReservationCreate,
    MarketplaceInventorySyncPlanGenerateRequest,
    MarketplaceOrderCreate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_inventory_availability import get_availability, list_availability
from app.services.marketplace_inventory_reservations import create_reservation, list_reservations, release_reservation
from app.services.marketplace_inventory_sync_planner import generate_sync_plan, get_sync_plan, list_sync_plans
from app.services.marketplace_orders import cancel_order, create_order, get_order, list_orders, mark_order_fulfilled, mark_order_paid

marketplace_sync_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Sync Safety Engine API v1"])


def attach_marketplace_sync_layer(app: FastAPI) -> None:
    app.include_router(marketplace_sync_v1_router)


@marketplace_sync_v1_router.get("/marketplace-sync/availability", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_availability(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_availability(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_sync_v1_router.get("/marketplace-sync/availability/{listing_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_sync_availability(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_availability(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_sync_v1_router.post("/marketplace-sync/reservations", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_marketplace_sync_reservation(
    payload: MarketplaceInventoryReservationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_reservation(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_sync_v1_router.get("/marketplace-sync/reservations", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_reservations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_reservations(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_sync_v1_router.post("/marketplace-sync/reservations/{reservation_id}/release", response_model=ScanApiV1Envelope)
def v1_release_marketplace_sync_reservation(
    reservation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = release_reservation(session, owner_id=int(current_user.id), reservation_id=reservation_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_sync_v1_router.post("/marketplace-sync/orders", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_marketplace_sync_order(
    payload: MarketplaceOrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_order(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.order.id)


@marketplace_sync_v1_router.get("/marketplace-sync/orders", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_orders(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_sync_v1_router.get("/marketplace-sync/orders/{order_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_sync_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_order(session, owner_id=int(current_user.id), order_id=order_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.order.id)


@marketplace_sync_v1_router.post("/marketplace-sync/orders/{order_id}/paid", response_model=ScanApiV1Envelope)
def v1_mark_marketplace_sync_order_paid(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_order_paid(session, owner_id=int(current_user.id), order_id=order_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.order.id)


@marketplace_sync_v1_router.post("/marketplace-sync/orders/{order_id}/fulfilled", response_model=ScanApiV1Envelope)
def v1_mark_marketplace_sync_order_fulfilled(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_order_fulfilled(session, owner_id=int(current_user.id), order_id=order_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.order.id)


@marketplace_sync_v1_router.post("/marketplace-sync/orders/{order_id}/cancel", response_model=ScanApiV1Envelope)
def v1_cancel_marketplace_sync_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = cancel_order(session, owner_id=int(current_user.id), order_id=order_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.order.id)


@marketplace_sync_v1_router.post("/marketplace-sync/plans/generate", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_generate_marketplace_sync_plan(
    payload: MarketplaceInventorySyncPlanGenerateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_sync_plan(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.plan.id)


@marketplace_sync_v1_router.get("/marketplace-sync/plans", response_model=ScanApiV1Envelope)
def v1_list_marketplace_sync_plans(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_sync_plans(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_sync_v1_router.get("/marketplace-sync/plans/{plan_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_sync_plan(
    plan_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_sync_plan(session, owner_id=int(current_user.id), plan_id=plan_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.plan.id)
