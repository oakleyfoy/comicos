"""Advisory dealer-intelligence routes backed by agent executions and research snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.catalog_intelligence_agent import run_catalog_intelligence_agent
from app.services.intelligence_engine import (
    get_recommendation_detail_for_owner,
    list_recommendation_types,
    list_recommendations,
)
from app.services.intelligence_review import mark_accepted, mark_dismissed, mark_reviewed
from app.services.pricing_intelligence_agent import run_pricing_intelligence_agent

intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Dealer Intelligence API v1"])


def attach_intelligence_layer(app: FastAPI) -> None:
    app.include_router(intelligence_v1_router)


@intelligence_v1_router.get("/intelligence/recommendations", response_model=ScanApiV1Envelope)
def v1_list_intelligence_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_type: str | None = Query(default=None),
    recommendation_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation_type=recommendation_type,
        status=recommendation_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@intelligence_v1_router.get("/intelligence/recommendations/types", response_model=ScanApiV1Envelope)
def v1_list_intelligence_recommendation_types(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    del session
    assert current_user.id is not None
    body = list_recommendation_types()
    return wrap_object(body, owner_user_id=int(current_user.id))


@intelligence_v1_router.get("/intelligence/recommendations/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_get_intelligence_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recommendation_detail_for_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@intelligence_v1_router.post("/intelligence/recommendations/{recommendation_id}/reviewed", response_model=ScanApiV1Envelope)
def v1_mark_intelligence_reviewed(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_reviewed(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@intelligence_v1_router.post("/intelligence/recommendations/{recommendation_id}/dismissed", response_model=ScanApiV1Envelope)
def v1_mark_intelligence_dismissed(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_dismissed(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@intelligence_v1_router.post("/intelligence/recommendations/{recommendation_id}/accepted", response_model=ScanApiV1Envelope)
def v1_mark_intelligence_accepted(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_accepted(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@intelligence_v1_router.post(
    "/intelligence/pricing-agent/run",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_pricing_intelligence_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_pricing_intelligence_agent(session, current_user=current_user)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot.id)


@intelligence_v1_router.post(
    "/intelligence/catalog-agent/run",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_catalog_intelligence_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_catalog_intelligence_agent(session, current_user=current_user)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot.id)
