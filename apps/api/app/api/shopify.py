from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.marketplace import MarketplaceAccount, MarketplaceExecution
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.shopify import ShopifyConnectRequest
from app.services.marketplace_execution import _execution_read
from app.services.shopify_accounts import (
    _shopify_marketplace_id,
    connect_account,
    disconnect_account,
    get_account_status,
    validate_account,
)
from app.services.shopify_inventory_sync import sync_availability, sync_inventory_plan
from app.services.shopify_order_import import import_orders
from app.services.shopify_product_publish import (
    archive_listing,
    publish_canonical_listing,
    restore_listing,
    update_canonical_listing,
)

shopify_v1_router = APIRouter(prefix="/api/v1", tags=["Shopify Integration API v1"])


def attach_shopify_layer(app: FastAPI) -> None:
    app.include_router(shopify_v1_router)


@shopify_v1_router.post("/shopify/connect", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_shopify_connect(
    payload: ShopifyConnectRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = connect_account(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shopify_v1_router.post("/shopify/disconnect", response_model=ScanApiV1Envelope)
def v1_shopify_disconnect(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = disconnect_account(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shopify_v1_router.get("/shopify/account", response_model=ScanApiV1Envelope)
def v1_shopify_account(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_account_status(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account_id)


@shopify_v1_router.post("/shopify/validate", response_model=ScanApiV1Envelope)
def v1_shopify_validate(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_account(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account_id)


@shopify_v1_router.post("/shopify/publish/{listing_id}", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_shopify_publish(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = publish_canonical_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@shopify_v1_router.post("/shopify/update/{listing_id}", response_model=ScanApiV1Envelope)
def v1_shopify_update(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_canonical_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@shopify_v1_router.post("/shopify/archive/{listing_id}", response_model=ScanApiV1Envelope)
def v1_shopify_archive(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = archive_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@shopify_v1_router.post("/shopify/restore/{listing_id}", response_model=ScanApiV1Envelope)
def v1_shopify_restore(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = restore_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing_id)


@shopify_v1_router.post("/shopify/import-orders", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_shopify_import_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = import_orders(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@shopify_v1_router.post("/shopify/sync-inventory", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_shopify_sync_inventory(
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


@shopify_v1_router.get("/shopify/executions", response_model=ScanApiV1Envelope)
def v1_shopify_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    marketplace_id = _shopify_marketplace_id(session)
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
