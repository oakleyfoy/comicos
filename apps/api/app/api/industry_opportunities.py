from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.industry_opportunity import IndustryOpportunityListRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.industry_opportunities import (
    build_industry_opportunity_summary,
    list_industry_opportunities,
    refresh_latest_industry_opportunities,
)

industry_opportunity_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Industry Opportunities API v1 (P59-04)"],
)


def attach_industry_opportunity_layer(app: FastAPI) -> None:
    app.include_router(industry_opportunity_v1_router)


@industry_opportunity_v1_router.get("/industry-opportunities", response_model=ScanApiV1Envelope)
def v1_list_industry_opportunities(
    scan_run_id: int | None = None,
    risk_level: str | None = None,
    opportunity_score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_industry_opportunities(
        session,
        owner_user_id=int(current_user.id),
        scan_run_id=scan_run_id,
        risk_level=risk_level,
        opportunity_score_min=opportunity_score_min,
        limit=limit,
        offset=offset,
    )
    body = IndustryOpportunityListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@industry_opportunity_v1_router.get("/industry-opportunities/latest", response_model=ScanApiV1Envelope)
def v1_latest_industry_opportunities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = refresh_latest_industry_opportunities(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@industry_opportunity_v1_router.get("/industry-opportunities/summary", response_model=ScanApiV1Envelope)
def v1_industry_opportunity_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_industry_opportunity_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
