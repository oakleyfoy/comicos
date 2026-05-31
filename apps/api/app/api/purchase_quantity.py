from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.purchase_quantity import PurchaseQuantityGenerateResponse, PurchaseQuantityListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.purchase_quantities import (
    generate_purchase_quantities,
    get_purchase_quantity_recommendation,
    list_latest_purchase_quantity_recommendations,
    list_purchase_quantity_recommendations,
)

purchase_quantity_v1_router = APIRouter(prefix="/api/v1", tags=["Purchase Quantities API v1 (P53-02)"])


def attach_purchase_quantity_layer(app: FastAPI) -> None:
    app.include_router(purchase_quantity_v1_router)


@purchase_quantity_v1_router.get("/purchase-quantities", response_model=ScanApiV1Envelope)
def v1_list_purchase_quantities(
    tier: str | None = None,
    quantity: int | None = Query(default=None, ge=0, le=5),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_purchase_quantity_recommendations(
        session,
        owner_user_id=int(current_user.id),
        tier=tier,
        quantity=quantity,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = PurchaseQuantityListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@purchase_quantity_v1_router.get("/purchase-quantities/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_purchase_quantities(
    tier: str | None = None,
    quantity: int | None = Query(default=None, ge=0, le=5),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_purchase_quantity_recommendations(
        session,
        owner_user_id=int(current_user.id),
        tier=tier,
        quantity=quantity,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = PurchaseQuantityListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@purchase_quantity_v1_router.post("/purchase-quantities/generate", response_model=ScanApiV1Envelope)
def v1_generate_purchase_quantities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    created = generate_purchase_quantities(session, owner_user_id=int(current_user.id))
    return wrap_object(PurchaseQuantityGenerateResponse(created_count=created), owner_user_id=int(current_user.id))


@purchase_quantity_v1_router.get("/purchase-quantities/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_get_purchase_quantity(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = get_purchase_quantity_recommendation(
            session,
            owner_user_id=int(current_user.id),
            recommendation_id=recommendation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))
