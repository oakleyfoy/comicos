"""P78-02 listings, sales, analytics, certification APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p78_marketplace import (
    P78ListingListResponse,
    P78ListingPublishRead,
    P78ListingSyncRead,
    P78ListingUpdate,
    P78SaleListResponse,
    P78SellingAnalyticsRead,
    P78SellingCertificationRead,
    P78SellingDashboardRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.p78_listing_lifecycle_service import (
    get_listing,
    get_sale,
    list_listings,
    list_sales,
    publish_listing,
    sync_listings,
    update_listing,
)
from app.services.p78_selling_analytics_service import build_selling_analytics, build_selling_dashboard
from app.services.selling_certification import run_selling_certification

p78_marketplace_v1_router = APIRouter(tags=["Sell Marketplace API v1 (P78-02)"])


def attach_p78_marketplace_layer(app: FastAPI) -> None:
    app.include_router(p78_marketplace_v1_router)


@p78_marketplace_v1_router.get("/api/v1/listings", response_model=ScanApiV1Envelope)
def v1_listings(
    lifecycle_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78ListingListResponse = list_listings(
        session,
        owner_user_id=int(current_user.id),
        lifecycle_status=lifecycle_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.get("/api/v1/listings/{listing_id}", response_model=ScanApiV1Envelope)
def v1_get_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_listing(session, owner_user_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.put("/api/v1/listings/{listing_id}", response_model=ScanApiV1Envelope)
def v1_update_listing(
    listing_id: int,
    payload: P78ListingUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_listing(session, owner_user_id=int(current_user.id), listing_id=listing_id, payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.post("/api/v1/listings/{listing_id}/publish", response_model=ScanApiV1Envelope)
def v1_publish_listing(
    listing_id: int,
    price_mode: str = Query("market"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78ListingPublishRead = publish_listing(
        session,
        owner_user_id=int(current_user.id),
        listing_id=listing_id,
        price_mode=price_mode,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.post("/api/v1/listings/sync", response_model=ScanApiV1Envelope)
def v1_sync_listings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78ListingSyncRead = sync_listings(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.get("/api/v1/sales", response_model=ScanApiV1Envelope)
def v1_sales(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78SaleListResponse = list_sales(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.get("/api/v1/sales/{sale_id}", response_model=ScanApiV1Envelope)
def v1_get_sale(
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_sale(session, owner_user_id=int(current_user.id), sale_id=sale_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.get("/api/v1/selling-analytics", response_model=ScanApiV1Envelope)
def v1_selling_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78SellingAnalyticsRead = build_selling_analytics(session, owner_user_id=int(current_user.id), persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.get("/api/v1/selling-dashboard", response_model=ScanApiV1Envelope)
def v1_selling_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78SellingDashboardRead = build_selling_dashboard(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_marketplace_v1_router.get("/api/v1/selling-certification", response_model=ScanApiV1Envelope)
def v1_selling_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78SellingCertificationRead = run_selling_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
