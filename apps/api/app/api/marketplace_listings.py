"""P43-02 `/api/v1/organizations/*/marketplace-listings` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_listing import (
    MarketplaceListingCreate,
    MarketplaceListingImageCreate,
    MarketplaceListingMappingCreate,
    MarketplaceListingPriceCreate,
    MarketplaceListingUpdate,
)
from app.schemas.marketplace_listings import (
    MarketplaceListingDraftCreateRequest,
    MarketplaceListingDraftUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_listing_images import add_listing_image, list_listing_images, set_primary_image
from app.services.marketplace_listing_mappings import create_mapping, list_mappings_for_listing
from app.services.marketplace_listing_prices import get_price_history, set_listing_price
from app.services.marketplace_listings import (
    archive_listing,
    create_listing,
    get_listing,
    list_listings,
    mark_ready_to_publish,
    update_listing,
)
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
canonical_marketplace_listings_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Catalog Listings API v1"])


def attach_marketplace_listings_layer(app: FastAPI) -> None:
    app.include_router(marketplace_listings_v1_router)
    app.include_router(canonical_marketplace_listings_v1_router)


@canonical_marketplace_listings_v1_router.get("/marketplace-listings", response_model=ScanApiV1Envelope)
def v1_list_canonical_marketplace_listings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_listings(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@canonical_marketplace_listings_v1_router.post(
    "/marketplace-listings",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_canonical_marketplace_listing(
    payload: MarketplaceListingCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_listing(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing.id)


@canonical_marketplace_listings_v1_router.get("/marketplace-listings/{listing_id}", response_model=ScanApiV1Envelope)
def v1_get_canonical_marketplace_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing.id)


@canonical_marketplace_listings_v1_router.patch("/marketplace-listings/{listing_id}", response_model=ScanApiV1Envelope)
def v1_update_canonical_marketplace_listing(
    listing_id: int,
    payload: MarketplaceListingUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_listing(session, owner_id=int(current_user.id), listing_id=listing_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing.id)


@canonical_marketplace_listings_v1_router.post("/marketplace-listings/{listing_id}/archive", response_model=ScanApiV1Envelope)
def v1_archive_canonical_marketplace_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = archive_listing(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing.id)


@canonical_marketplace_listings_v1_router.post(
    "/marketplace-listings/{listing_id}/ready-to-publish",
    response_model=ScanApiV1Envelope,
)
def v1_mark_canonical_marketplace_listing_ready(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_ready_to_publish(session, owner_id=int(current_user.id), listing_id=listing_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.listing.id)


@canonical_marketplace_listings_v1_router.get("/marketplace-listings/{listing_id}/prices", response_model=ScanApiV1Envelope)
def v1_list_canonical_marketplace_listing_prices(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_price_history(session, owner_id=int(current_user.id), listing_id=listing_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@canonical_marketplace_listings_v1_router.post(
    "/marketplace-listings/{listing_id}/prices",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_set_canonical_marketplace_listing_price(
    listing_id: int,
    payload: MarketplaceListingPriceCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = set_listing_price(session, owner_id=int(current_user.id), listing_id=listing_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@canonical_marketplace_listings_v1_router.get("/marketplace-listings/{listing_id}/images", response_model=ScanApiV1Envelope)
def v1_list_canonical_marketplace_listing_images(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_listing_images(session, owner_id=int(current_user.id), listing_id=listing_id, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@canonical_marketplace_listings_v1_router.post(
    "/marketplace-listings/{listing_id}/images",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_add_canonical_marketplace_listing_image(
    listing_id: int,
    payload: MarketplaceListingImageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = add_listing_image(session, owner_id=int(current_user.id), listing_id=listing_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@canonical_marketplace_listings_v1_router.post(
    "/marketplace-listings/{listing_id}/images/{image_id}/primary",
    response_model=ScanApiV1Envelope,
)
def v1_set_canonical_marketplace_listing_primary_image(
    listing_id: int,
    image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = set_primary_image(session, owner_id=int(current_user.id), listing_id=listing_id, image_id=image_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@canonical_marketplace_listings_v1_router.get("/marketplace-listings/{listing_id}/mappings", response_model=ScanApiV1Envelope)
def v1_list_canonical_marketplace_listing_mappings(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_mappings_for_listing(
        session,
        owner_id=int(current_user.id),
        listing_id=listing_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@canonical_marketplace_listings_v1_router.post(
    "/marketplace-listings/{listing_id}/mappings",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_canonical_marketplace_listing_mapping(
    listing_id: int,
    payload: MarketplaceListingMappingCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_mapping(session, owner_id=int(current_user.id), listing_id=listing_id, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


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
