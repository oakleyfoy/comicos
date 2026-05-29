"""P43-08 `/api/v1/organizations/*/shopify` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.shopify_sync import (
    ShopifyProductMappingCreateRequest,
    ShopifyProductMappingUpdateRequest,
    ShopifyStorefrontCreateRequest,
    ShopifySyncSnapshotRequest,
)
from app.services.shopify_mapping_service import (
    create_product_mapping,
    list_product_mappings,
    update_product_mapping,
)
from app.services.shopify_sync_service import (
    create_storefront,
    generate_storefront_sync_snapshot,
    get_shopify_overview,
    list_sync_states,
)

shopify_sync_v1_router = APIRouter(prefix="/api/v1", tags=["Shopify Sync API v1 (P43-08)"])


def attach_shopify_sync_layer(app: FastAPI) -> None:
    app.include_router(shopify_sync_v1_router)


@shopify_sync_v1_router.get("/organizations/{organization_id}/shopify", response_model=ScanApiV1Envelope)
def v1_get_shopify_overview(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_shopify_overview(session, organization_id=organization_id, actor_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@shopify_sync_v1_router.get("/organizations/{organization_id}/shopify/mappings", response_model=ScanApiV1Envelope)
def v1_list_shopify_mappings(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_product_mappings(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@shopify_sync_v1_router.get("/organizations/{organization_id}/shopify/sync-states", response_model=ScanApiV1Envelope)
def v1_list_shopify_sync_states(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_sync_states(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@shopify_sync_v1_router.post(
    "/organizations/{organization_id}/shopify/storefront",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_shopify_storefront(
    organization_id: int,
    payload: ShopifyStorefrontCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_storefront(session, organization_id=organization_id, actor_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shopify_sync_v1_router.post(
    "/organizations/{organization_id}/shopify/mappings",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_shopify_mapping(
    organization_id: int,
    payload: ShopifyProductMappingCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_product_mapping(session, organization_id=organization_id, actor_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@shopify_sync_v1_router.post(
    "/organizations/{organization_id}/shopify/snapshot",
    response_model=ScanApiV1Envelope,
)
def v1_generate_shopify_snapshot(
    organization_id: int,
    payload: ShopifySyncSnapshotRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_storefront_sync_snapshot(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        storefront_id=payload.storefront_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=payload.storefront_id)


@shopify_sync_v1_router.patch("/organizations/{organization_id}/shopify/mappings/{mapping_id}", response_model=ScanApiV1Envelope)
def v1_update_shopify_mapping(
    organization_id: int,
    mapping_id: int,
    payload: ShopifyProductMappingUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_product_mapping(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        mapping_id=mapping_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
