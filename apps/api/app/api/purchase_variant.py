from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.purchase_variant import (
    PurchaseVariantGenerateResponse,
    PurchaseVariantRecommendationListRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.purchase_variants import (
    generate_purchase_variants,
    get_purchase_variant_recommendation,
    list_latest_purchase_variant_recommendations,
    list_purchase_variant_recommendations,
)

purchase_variant_v1_router = APIRouter(prefix="/api/v1", tags=["Purchase Variants API v1 (P53-03)"])


def attach_purchase_variant_layer(app: FastAPI) -> None:
    app.include_router(purchase_variant_v1_router)


@purchase_variant_v1_router.get("/purchase-variants", response_model=ScanApiV1Envelope)
def v1_list_purchase_variants(
    recommendation: str | None = None,
    variant_type: str | None = None,
    publisher: str | None = None,
    release_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_purchase_variant_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        variant_type=variant_type,
        publisher=publisher,
        release_id=release_id,
        limit=limit,
        offset=offset,
    )
    body = PurchaseVariantRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@purchase_variant_v1_router.get("/purchase-variants/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_purchase_variants(
    recommendation: str | None = None,
    variant_type: str | None = None,
    publisher: str | None = None,
    release_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_purchase_variant_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        variant_type=variant_type,
        publisher=publisher,
        release_id=release_id,
        limit=limit,
        offset=offset,
    )
    body = PurchaseVariantRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@purchase_variant_v1_router.post("/purchase-variants/generate", response_model=ScanApiV1Envelope)
def v1_generate_purchase_variants(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    created = generate_purchase_variants(session, owner_user_id=int(current_user.id))
    return wrap_object(PurchaseVariantGenerateResponse(created_count=created), owner_user_id=int(current_user.id))


@purchase_variant_v1_router.get("/purchase-variants/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_get_purchase_variant(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_purchase_variant_recommendation(
            session,
            owner_user_id=int(current_user.id),
            recommendation_id=recommendation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))
