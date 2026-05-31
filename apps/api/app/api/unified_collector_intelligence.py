from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.unified_collector_intelligence import UnifiedCollectorListResponse
from app.services.unified_collector_intelligence import (
    get_unified_collector_summary,
    list_latest_unified_collector_recommendations,
    refresh_and_list_latest_unified_collector_recommendations,
)

unified_collector_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Unified Collector Intelligence API v1 (P57-01)"],
)


def attach_unified_collector_intelligence_layer(app: FastAPI) -> None:
    app.include_router(unified_collector_v1_router)


@unified_collector_v1_router.get("/unified-intelligence", response_model=ScanApiV1Envelope)
def v1_unified_intelligence(
    recommendation_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    source_system: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_unified_collector_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation_type=recommendation_type,
        priority_min=priority_min,
        source_system=source_system,
        limit=limit,
        offset=offset,
    )
    body = UnifiedCollectorListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@unified_collector_v1_router.get("/unified-intelligence/latest", response_model=ScanApiV1Envelope)
def v1_unified_intelligence_latest(
    recommendation_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    source_system: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_latest_unified_collector_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation_type=recommendation_type,
        priority_min=priority_min,
        source_system=source_system,
        limit=limit,
        offset=offset,
    )
    body = UnifiedCollectorListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@unified_collector_v1_router.get("/unified-intelligence/summary", response_model=ScanApiV1Envelope)
def v1_unified_intelligence_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.unified_collector_intelligence import generate_unified_collector_recommendations

    generate_unified_collector_recommendations(session, owner_user_id=int(current_user.id))
    body = get_unified_collector_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
