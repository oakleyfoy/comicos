from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.hold_sell_intelligence import HoldSellRecommendationListRead, HoldSellSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.hold_sell_intelligence import (
    build_hold_sell_summary,
    list_hold_sell_recommendations,
    refresh_and_list_latest_hold_sell,
)

hold_sell_v1_router = APIRouter(prefix="/api/v1", tags=["Hold vs Sell Intelligence API v1 (P56-02)"])


def attach_hold_sell_intelligence_layer(app: FastAPI) -> None:
    app.include_router(hold_sell_v1_router)


@hold_sell_v1_router.get("/hold-sell", response_model=ScanApiV1Envelope)
def v1_list_hold_sell(
    recommendation: str | None = None,
    conviction_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_hold_sell_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        conviction_min=conviction_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = HoldSellRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@hold_sell_v1_router.get("/hold-sell/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_hold_sell(
    recommendation: str | None = None,
    conviction_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_hold_sell(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        conviction_min=conviction_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = HoldSellRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@hold_sell_v1_router.get("/hold-sell/summary", response_model=ScanApiV1Envelope)
def v1_hold_sell_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_hold_sell_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
