from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.grade_before_sell import GradeBeforeSellRecommendationListRead, GradeBeforeSellSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.grade_before_sell import (
    build_grade_before_sell_summary,
    list_grade_before_sell_recommendations,
    refresh_and_list_latest_grade_before_sell,
)

grade_before_sell_v1_router = APIRouter(prefix="/api/v1", tags=["Grade Before Sell API v1 (P56-03)"])


def attach_grade_before_sell_layer(app: FastAPI) -> None:
    app.include_router(grade_before_sell_v1_router)


@grade_before_sell_v1_router.get("/grade-before-sell", response_model=ScanApiV1Envelope)
def v1_list_grade_before_sell(
    recommendation: str | None = None,
    roi_min: float | None = Query(default=None),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_grade_before_sell_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        roi_min=roi_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = GradeBeforeSellRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grade_before_sell_v1_router.get("/grade-before-sell/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_grade_before_sell(
    recommendation: str | None = None,
    roi_min: float | None = Query(default=None),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_grade_before_sell(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        roi_min=roi_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = GradeBeforeSellRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@grade_before_sell_v1_router.get("/grade-before-sell/summary", response_model=ScanApiV1Envelope)
def v1_grade_before_sell_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_grade_before_sell_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
