from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.marketplace import MarketplaceAccount, MarketplaceExecution
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.whatnot import WhatnotConnectRequest
from app.services.marketplace_execution import _execution_read
from app.services.whatnot_accounts import (
    connect_account,
    disconnect_account,
    get_account_status,
    validate_account,
)
from app.services.whatnot_inventory_sync import sync_availability, sync_inventory_plan
from app.services.whatnot_listing_publish import pause_listing, publish_canonical_listing, resume_listing, update_canonical_listing
from app.services.whatnot_order_import import import_orders
from app.services.whatnot_accounts import _whatnot_marketplace_id

whatnot_v1_router = APIRouter(prefix="/api/v1", tags=["Whatnot Integration API v1"])


def attach_whatnot_layer(app: FastAPI) -> None:
    app.include_router(whatnot_v1_router)


@whatnot_v1_router.post("/whatnot/connect", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_whatnot_connect(
    payload: WhatnotConnectRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = connect_account(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@whatnot_v1_router.post("/whatnot/disconnect", response_model=ScanApiV1Envelope)
def v1_whatnot_disconnect(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = disconnect_account(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@whatnot_v1_router.get("/whatnot/account", response_model=ScanApiV1Envelope)
def v1_whatnot_account(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_account_status(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account_id)


@whatnot_v1_router.post("/whatnot/validate", response_model=ScanApiV1Envelope)
def v1_whatnot_validate(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_account(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account_id)


@whatnot_v1_router.post("/whatnot/publish/{listing_id}", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_whatnot_publish(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = publish_canonical_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@whatnot_v1_router.post("/whatnot/update/{listing_id}", response_model=ScanApiV1Envelope)
def v1_whatnot_update(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_canonical_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@whatnot_v1_router.post("/whatnot/pause/{listing_id}", response_model=ScanApiV1Envelope)
def v1_whatnot_pause(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = pause_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@whatnot_v1_router.post("/whatnot/resume/{listing_id}", response_model=ScanApiV1Envelope)
def v1_whatnot_resume(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = resume_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@whatnot_v1_router.post("/whatnot/import-orders", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_whatnot_import_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = import_orders(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@whatnot_v1_router.post("/whatnot/sync-inventory", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_whatnot_sync_inventory(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    listing_id: int | None = Query(default=None, gt=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if listing_id is not None:
        body = sync_availability(session, owner_id=int(current_user.id), listing_id=listing_id)
    else:
        body = sync_inventory_plan(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.plan_id)


@whatnot_v1_router.get("/whatnot/executions", response_model=ScanApiV1Envelope)
def v1_whatnot_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    marketplace_id = _whatnot_marketplace_id(session)
    rows = session.exec(
        select(MarketplaceExecution)
        .join(MarketplaceAccount, MarketplaceAccount.id == MarketplaceExecution.account_id)
        .where(MarketplaceAccount.owner_id == int(current_user.id))
        .where(MarketplaceExecution.marketplace_id == marketplace_id)
        .order_by(MarketplaceExecution.created_at.desc(), MarketplaceExecution.id.desc())
    ).all()
    items = [_execution_read(row) for row in rows]
    from app.schemas.marketplace import MarketplaceExecutionListResponse

    body = MarketplaceExecutionListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
