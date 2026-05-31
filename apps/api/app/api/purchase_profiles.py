from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.purchase_profile import PurchasePreferenceUpdate, PurchaseProfileUpdate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.purchase_profiles import (
    get_purchase_preferences,
    get_purchase_profile,
    set_purchase_profile,
    update_purchase_preferences,
)

purchase_profile_v1_router = APIRouter(prefix="/api/v1", tags=["Purchase Profile API v1 (P53-01)"])


def attach_purchase_profile_layer(app: FastAPI) -> None:
    app.include_router(purchase_profile_v1_router)


@purchase_profile_v1_router.get("/purchase-profile", response_model=ScanApiV1Envelope)
def v1_get_purchase_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_purchase_profile(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@purchase_profile_v1_router.patch("/purchase-profile", response_model=ScanApiV1Envelope)
def v1_patch_purchase_profile(
    payload: PurchaseProfileUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = set_purchase_profile(session, owner_user_id=int(current_user.id), payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@purchase_profile_v1_router.get("/purchase-profile/preferences", response_model=ScanApiV1Envelope)
def v1_get_purchase_preferences(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_purchase_preferences(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@purchase_profile_v1_router.patch("/purchase-profile/preferences", response_model=ScanApiV1Envelope)
def v1_patch_purchase_preferences(
    payload: PurchasePreferenceUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_purchase_preferences(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))
