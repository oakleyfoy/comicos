from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.purchase_budget import (
    PurchaseBudgetAllocationListRead,
    PurchaseBudgetGenerateResponse,
    PurchaseBudgetUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.purchase_budgets import (
    build_purchase_budget_summary,
    generate_purchase_budget_allocations,
    get_purchase_budget,
    list_purchase_budget_allocations,
    update_purchase_budget,
)

purchase_budget_v1_router = APIRouter(prefix="/api/v1", tags=["Purchase Budget API v1 (P53-04)"])


def attach_purchase_budget_layer(app: FastAPI) -> None:
    app.include_router(purchase_budget_v1_router)


@purchase_budget_v1_router.get("/purchase-budget", response_model=ScanApiV1Envelope)
def v1_get_purchase_budget(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_purchase_budget(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@purchase_budget_v1_router.patch("/purchase-budget", response_model=ScanApiV1Envelope)
def v1_patch_purchase_budget(
    payload: PurchaseBudgetUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        body = update_purchase_budget(session, owner_user_id=int(current_user.id), payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return wrap_object(body, owner_user_id=int(current_user.id))


@purchase_budget_v1_router.get("/purchase-budget/allocations", response_model=ScanApiV1Envelope)
def v1_list_purchase_budget_allocations(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_purchase_budget_allocations(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = PurchaseBudgetAllocationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@purchase_budget_v1_router.get("/purchase-budget/summary", response_model=ScanApiV1Envelope)
def v1_purchase_budget_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_purchase_budget_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@purchase_budget_v1_router.post("/purchase-budget/allocations/generate", response_model=ScanApiV1Envelope)
def v1_generate_purchase_budget_allocations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    created = generate_purchase_budget_allocations(session, owner_user_id=int(current_user.id))
    return wrap_object(PurchaseBudgetGenerateResponse(created_count=created), owner_user_id=int(current_user.id))
