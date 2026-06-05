from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.cross_system_recommendation import (
    CrossSystemRecommendationListResponse,
    CrossSystemRecommendationRebuildRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.cross_system_recommendation import (
    get_cross_system_recommendation_summary,
    list_latest_cross_system_recommendations,
    rebuild_cross_system_recommendations,
)

cross_system_recommendation_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Cross-System Recommendation API v1 (P57-03)"],
)


def attach_cross_system_recommendation_layer(app: FastAPI) -> None:
    app.include_router(cross_system_recommendation_v1_router)


@cross_system_recommendation_v1_router.get("/cross-system-recommendations", response_model=ScanApiV1Envelope)
def v1_cross_system_recommendations(
    recommendation_type: str | None = None,
    rank_max: int | None = Query(default=None, ge=1, le=500),
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_cross_system_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation_type=recommendation_type,
        rank_max=rank_max,
        priority_min=priority_min,
        limit=limit,
        offset=offset,
    )
    body = CrossSystemRecommendationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@cross_system_recommendation_v1_router.get("/cross-system-recommendations/latest", response_model=ScanApiV1Envelope)
def v1_cross_system_recommendations_latest(
    recommendation_type: str | None = None,
    rank_max: int | None = Query(default=None, ge=1, le=500),
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_cross_system_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation_type=recommendation_type,
        rank_max=rank_max,
        priority_min=priority_min,
        limit=limit,
        offset=offset,
    )
    body = CrossSystemRecommendationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@cross_system_recommendation_v1_router.get("/cross-system-recommendations/summary", response_model=ScanApiV1Envelope)
def v1_cross_system_recommendations_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_cross_system_recommendation_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@cross_system_recommendation_v1_router.post("/cross-system-recommendations/rebuild", response_model=ScanApiV1Envelope)
def v1_cross_system_recommendations_rebuild(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows = rebuild_cross_system_recommendations(session, owner_user_id=int(current_user.id), refresh_upstream=True)
    body = CrossSystemRecommendationRebuildRead(rows_persisted=int(rows), readiness_status="READY")
    return wrap_object(body, owner_user_id=int(current_user.id))
