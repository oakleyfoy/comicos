from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.acquisition_opportunity import AcquisitionOpportunityListRead, AcquisitionOpportunitySummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.acquisition_opportunities import (
    build_acquisition_opportunity_summary,
    list_acquisition_opportunities,
    refresh_and_list_latest_acquisition_opportunities,
)

acquisition_opportunity_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Acquisition Opportunities API v1 (P55-03)"],
)


def attach_acquisition_opportunity_layer(app: FastAPI) -> None:
    app.include_router(acquisition_opportunity_v1_router)


@acquisition_opportunity_v1_router.get("/acquisition-opportunities", response_model=ScanApiV1Envelope)
def v1_list_acquisition_opportunities(
    opportunity_type: str | None = None,
    priority_score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_acquisition_opportunities(
        session,
        owner_user_id=int(current_user.id),
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = AcquisitionOpportunityListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@acquisition_opportunity_v1_router.get("/acquisition-opportunities/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_acquisition_opportunities(
    opportunity_type: str | None = None,
    priority_score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_acquisition_opportunities(
        session,
        owner_user_id=int(current_user.id),
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = AcquisitionOpportunityListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@acquisition_opportunity_v1_router.get("/acquisition-opportunities/summary", response_model=ScanApiV1Envelope)
def v1_acquisition_opportunity_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_acquisition_opportunity_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
