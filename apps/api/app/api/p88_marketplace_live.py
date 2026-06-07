"""P88-02 live marketplace APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.p88_marketplace_live import (
    MarketplaceListingListResponse,
    MarketplaceSearchDashboardRead,
    MarketplaceSearchMarketplacePayload,
    MarketplaceSearchMarketplaceResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace.marketplace_listing_read_service import (
    list_opportunity_listings,
    marketplace_search_dashboard,
)
from app.services.marketplace.marketplace_listing_refresh_service import refresh_listings_for_owner
from app.services.marketplace.marketplace_live_search_service import run_marketplace_search_for_user
from app.services.ops_access import is_ops_admin_user

p88_live_router = APIRouter(tags=["Marketplace Live (P88-02)"])


def attach_p88_marketplace_live_layer(app: FastAPI) -> None:
    app.include_router(p88_live_router)


@p88_live_router.post("/api/v1/buy-opportunities/search-marketplace", response_model=ScanApiV1Envelope)
def v1_search_buy_opportunity_marketplace(
    payload: MarketplaceSearchMarketplacePayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    ids = payload.opportunity_ids if payload else []
    body: MarketplaceSearchMarketplaceResponse = run_marketplace_search_for_user(
        session,
        owner_user_id=int(current_user.id),
        opportunity_ids=ids or None,
        settings=settings,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_live_router.get("/api/v1/buy-opportunities/{opportunity_id}/listings", response_model=ScanApiV1Envelope)
def v1_list_opportunity_marketplace_listings(
    opportunity_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceListingListResponse = list_opportunity_listings(
        session,
        owner_user_id=int(current_user.id),
        opportunity_id=opportunity_id,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p88_live_router.post("/api/v1/buy-opportunities/refresh-listings", response_model=ScanApiV1Envelope)
def v1_refresh_marketplace_listings(
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    refreshed, ended, invalid = refresh_listings_for_owner(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        settings=settings,
    )
    session.commit()
    return wrap_object(
        {"refreshed": refreshed, "ended": ended, "invalid": invalid},
        owner_user_id=int(current_user.id),
    )


@p88_live_router.get("/api/v1/admin/marketplace-search-dashboard", response_model=ScanApiV1Envelope)
def v1_admin_marketplace_search_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    if not is_ops_admin_user(current_user, settings):
        raise HTTPException(status_code=403, detail="Admin access required.")
    body: MarketplaceSearchDashboardRead = marketplace_search_dashboard(session)
    return wrap_object(body, owner_user_id=int(current_user.id))
