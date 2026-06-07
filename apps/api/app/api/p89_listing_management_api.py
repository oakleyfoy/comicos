from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.p89_managed_listing import P89ManagedListing
from app.schemas.p89_listing_management import (
    P89ManagedListingCreate,
    P89ManagedListingInventorySoldRead,
    P89ManagedListingListRead,
    P89ManagedListingMarkSold,
    P89ManagedListingPortfolioSummaryRead,
    P89ManagedListingProfitRead,
    P89ManagedListingRead,
    P89ManagedListingStatusEventRead,
    P89ManagedListingUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.listing_management_service import (
    archive_managed_listing,
    build_portfolio_listing_summary,
    cancel_managed_listing,
    create_managed_listing,
    create_managed_listing_from_draft,
    listing_display_meta,
    listing_status_history,
    list_managed_listings,
    mark_inventory_sold_for_listing,
    mark_listing_active,
    mark_listing_expired,
    mark_listing_sold,
    update_managed_listing,
)
from app.services.listing_profit_service import calculate_listing_profit

p89_listing_management_router = APIRouter(tags=["Listing Management (P89-04)"])


def attach_p89_listing_management_layer(app: FastAPI) -> None:
    app.include_router(p89_listing_management_router)


def _profit_read(session: Session, row: P89ManagedListing) -> P89ManagedListingProfitRead | None:
    if row.status != "SOLD" and row.sale_price is None:
        return None
    b = calculate_listing_profit(session, listing=row)
    return P89ManagedListingProfitRead(
        gross_sale=b.gross_sale,
        total_costs=b.total_costs,
        net_profit=b.net_profit,
        profit_margin=b.profit_margin,
        cost_basis=b.cost_basis,
        cost_basis_known=b.cost_basis_known,
    )


def _to_read(session: Session, row: P89ManagedListing) -> P89ManagedListingRead:
    extra = listing_display_meta(session, row=row)
    history = [
        P89ManagedListingStatusEventRead(status=str(e.get("status") or ""), at=str(e.get("at") or ""))
        for e in listing_status_history(row)
    ]
    return P89ManagedListingRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        inventory_copy_id=int(row.inventory_copy_id),
        listing_draft_id=row.listing_draft_id,
        marketplace=row.marketplace,  # type: ignore[arg-type]
        listing_url=row.listing_url,
        external_listing_id=row.external_listing_id,
        title=row.title,
        comic_title=str(extra.get("comic_title") or ""),
        asking_price=row.asking_price,
        shipping_price=row.shipping_price,
        minimum_price=row.minimum_price,
        status=row.status,  # type: ignore[arg-type]
        listed_at=row.listed_at,
        sold_at=row.sold_at,
        expired_at=row.expired_at,
        archived_at=row.archived_at,
        sale_price=row.sale_price,
        shipping_charged=row.shipping_charged,
        marketplace_fees=row.marketplace_fees,
        shipping_cost=row.shipping_cost,
        net_profit=row.net_profit,
        notes=row.notes,
        profit=_profit_read(session, row),
        status_history=history,
        inventory_auto_updated=False,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _get_row(session: Session, *, owner_user_id: int, listing_id: int) -> P89ManagedListing:
    row = session.get(P89ManagedListing, listing_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Managed listing not found")
    return row


@p89_listing_management_router.post(
    "/api/v1/listing-management",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_managed_listing(
    payload: P89ManagedListingCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    uid = int(current_user.id)
    if payload.listing_draft_id is not None:
        row = create_managed_listing_from_draft(session, owner_user_id=uid, listing_draft_id=payload.listing_draft_id)
    else:
        if payload.inventory_copy_id is None:
            raise HTTPException(status_code=400, detail="inventory_copy_id is required when listing_draft_id is omitted")
        row = create_managed_listing(
            session,
            owner_user_id=uid,
            inventory_copy_id=payload.inventory_copy_id,
            marketplace=payload.marketplace,
            title=payload.title,
            asking_price=payload.asking_price,
            shipping_price=payload.shipping_price,
            minimum_price=payload.minimum_price,
            listing_url=payload.listing_url,
            external_listing_id=payload.external_listing_id,
            notes=payload.notes,
        )
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=uid)


@p89_listing_management_router.get("/api/v1/listing-management/portfolio-summary", response_model=ScanApiV1Envelope)
def v1_listing_management_portfolio_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = P89ManagedListingPortfolioSummaryRead(**build_portfolio_listing_summary(session, owner_user_id=int(current_user.id)))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p89_listing_management_router.get("/api/v1/listing-management", response_model=ScanApiV1Envelope)
def v1_list_managed_listings(
    status: str | None = None,
    marketplace: str | None = None,
    inventory_copy_id: int | None = None,
    listed_from: datetime | None = None,
    listed_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_managed_listings(
        session,
        owner_user_id=int(current_user.id),
        status=status,
        marketplace=marketplace,
        inventory_copy_id=inventory_copy_id,
        listed_from=listed_from,
        listed_to=listed_to,
        limit=limit,
        offset=offset,
    )
    body = P89ManagedListingListRead(
        items=[_to_read(session, r) for r in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p89_listing_management_router.get("/api/v1/listing-management/{listing_id}", response_model=ScanApiV1Envelope)
def v1_get_managed_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = _get_row(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.patch("/api/v1/listing-management/{listing_id}", response_model=ScanApiV1Envelope)
def v1_patch_managed_listing(
    listing_id: int,
    payload: P89ManagedListingUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = update_managed_listing(
        session,
        owner_user_id=int(current_user.id),
        listing_id=listing_id,
        fields=payload.model_dump(exclude_unset=True),
    )
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.post("/api/v1/listing-management/{listing_id}/mark-active", response_model=ScanApiV1Envelope)
def v1_mark_managed_listing_active(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = mark_listing_active(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.post("/api/v1/listing-management/{listing_id}/mark-sold", response_model=ScanApiV1Envelope)
def v1_mark_managed_listing_sold(
    listing_id: int,
    payload: P89ManagedListingMarkSold,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = mark_listing_sold(
        session,
        owner_user_id=int(current_user.id),
        listing_id=listing_id,
        sale_price=payload.sale_price,
        shipping_charged=payload.shipping_charged,
        marketplace_fees=payload.marketplace_fees,
        shipping_cost=payload.shipping_cost,
        sold_at=payload.sold_at,
    )
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.post("/api/v1/listing-management/{listing_id}/mark-expired", response_model=ScanApiV1Envelope)
def v1_mark_managed_listing_expired(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = mark_listing_expired(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.post("/api/v1/listing-management/{listing_id}/archive", response_model=ScanApiV1Envelope)
def v1_archive_managed_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = archive_managed_listing(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.post("/api/v1/listing-management/{listing_id}/cancel", response_model=ScanApiV1Envelope)
def v1_cancel_managed_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    row = cancel_managed_listing(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    session.commit()
    return wrap_object(_to_read(session, row), owner_user_id=int(current_user.id))


@p89_listing_management_router.post(
    "/api/v1/listing-management/{listing_id}/mark-inventory-sold",
    response_model=ScanApiV1Envelope,
)
def v1_mark_inventory_sold_for_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    result = mark_inventory_sold_for_listing(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    session.commit()
    body = P89ManagedListingInventorySoldRead(**result)
    return wrap_object(body, owner_user_id=int(current_user.id))
