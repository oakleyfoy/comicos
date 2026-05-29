from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Organization, User
from app.schemas.dealer_storefront import (
    DealerProfileUpsertRequest,
    DealerStorefrontSettingsUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.dealer_profile_service import (
    create_or_update_dealer_profile,
    list_featured_inventory,
    list_public_storefront_inventory,
    resolve_storefront_by_slug,
    update_storefront_settings,
)
from app.services.storefront_visibility_service import validate_storefront_access

storefronts_v1_router = APIRouter(prefix="/api/v1", tags=["Dealer Storefronts API v1 (P42-06)"])


def attach_storefronts_layer(app: FastAPI) -> None:
    app.include_router(storefronts_v1_router)


def _require_storefront_manage(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> User:
    assert current_user.id is not None
    validate_storefront_access(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return current_user


def _owner_user_id_for_org(session: Session, organization_id: int) -> int | None:
    organization = session.get(Organization, organization_id)
    if organization is None:
        return None
    return int(organization.owner_user_id)


@storefronts_v1_router.get("/storefronts/{public_slug}", response_model=ScanApiV1Envelope)
def v1_get_public_storefront(
    public_slug: str,
    session: Session = Depends(get_session),
) -> ScanApiV1Envelope:
    body = resolve_storefront_by_slug(session, public_slug=public_slug)
    return wrap_object(body, owner_user_id=_owner_user_id_for_org(session, body.profile.organization_id), snapshot_id=body.profile.id)


@storefronts_v1_router.get("/storefronts/{public_slug}/inventory", response_model=ScanApiV1Envelope)
def v1_get_public_storefront_inventory(
    public_slug: str,
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    body = list_public_storefront_inventory(session, public_slug=public_slug, limit=limit, offset=offset)
    profile = resolve_storefront_by_slug(session, public_slug=public_slug)
    return wrap_standard_list(body, owner_user_id=_owner_user_id_for_org(session, profile.profile.organization_id))


@storefronts_v1_router.get("/storefronts/{public_slug}/featured", response_model=ScanApiV1Envelope)
def v1_get_public_storefront_featured(
    public_slug: str,
    session: Session = Depends(get_session),
) -> ScanApiV1Envelope:
    body = list_featured_inventory(session, public_slug=public_slug)
    profile = resolve_storefront_by_slug(session, public_slug=public_slug)
    return wrap_standard_list(body, owner_user_id=_owner_user_id_for_org(session, profile.profile.organization_id))


@storefronts_v1_router.post("/organizations/{organization_id}/storefront/profile", response_model=ScanApiV1Envelope)
def v1_upsert_dealer_profile(
    organization_id: int,
    payload: DealerProfileUpsertRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(_require_storefront_manage),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_or_update_dealer_profile(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@storefronts_v1_router.post("/organizations/{organization_id}/storefront/settings", response_model=ScanApiV1Envelope)
def v1_update_storefront_settings(
    organization_id: int,
    payload: DealerStorefrontSettingsUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(_require_storefront_manage),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_storefront_settings(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
