"""P43-02 `/api/v1/organizations/*/marketplace-listings` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_listings import (
    MarketplaceListingDraftCreateRequest,
    MarketplaceListingDraftUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_listing_service import (
    archive_listing_draft,
    create_listing_draft,
    generate_projection_for_draft,
    get_listing_draft,
    list_listing_drafts,
    list_projections_for_draft,
    update_listing_draft,
)

marketplace_listings_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Listings API v1 (P43-02)"])


def attach_marketplace_listings_layer(app: FastAPI) -> None:
    app.include_router(marketplace_listings_v1_router)


@marketplace_listings_v1_router.get("/organizations/{organization_id}/marketplace-listings", response_model=ScanApiV1Envelope)
def v1_list_marketplace_listings(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_listing_drafts(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_listings_v1_router.get(
    "/organizations/{organization_id}/marketplace-listings/{listing_id}",
    response_model=ScanApiV1Envelope,
)
def v1_get_marketplace_listing(
    organization_id: int,
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        listing_id=listing_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.draft.id)


@marketplace_listings_v1_router.get(
    "/organizations/{organization_id}/marketplace-listings/{listing_id}/projections",
    response_model=ScanApiV1Envelope,
)
def v1_list_marketplace_listing_projections(
    organization_id: int,
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_projections_for_draft(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        listing_id=listing_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_listings_v1_router.post(
    "/organizations/{organization_id}/marketplace-listings",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_marketplace_listing(
    organization_id: int,
    payload: MarketplaceListingDraftCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.draft.id)


@marketplace_listings_v1_router.patch(
    "/organizations/{organization_id}/marketplace-listings/{listing_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_marketplace_listing(
    organization_id: int,
    listing_id: int,
    payload: MarketplaceListingDraftUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        listing_id=listing_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.draft.id)


@marketplace_listings_v1_router.post(
    "/organizations/{organization_id}/marketplace-listings/{listing_id}/projection",
    response_model=ScanApiV1Envelope,
)
def v1_generate_marketplace_listing_projection(
    organization_id: int,
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_projection_for_draft(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        listing_id=listing_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.draft.id)


@marketplace_listings_v1_router.post(
    "/organizations/{organization_id}/marketplace-listings/{listing_id}/archive",
    response_model=ScanApiV1Envelope,
)
def v1_archive_marketplace_listing(
    organization_id: int,
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = archive_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        listing_id=listing_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.draft.id)
