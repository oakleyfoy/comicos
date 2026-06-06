"""P80-03 collector shopping assistant (`/api/v1/collector/*`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p80_collector_assistant import (
    P80CollectorGapListResponse,
    P80CollectorOpportunityListResponse,
    P80CollectorPriceEvalRequest,
    P80CollectorPriceEvalResultRead,
    P80CollectorScanRequest,
    P80CollectorScanResultRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.p80_collector_assistant_service import (
    build_collector_dashboard,
    evaluate_collector_price,
    evaluate_collector_scan,
    list_collector_gaps,
    list_collector_opportunities,
)

p80_collector_assistant_v1_router = APIRouter(
    prefix="/api/v1/collector",
    tags=["Collector Assistant API v1 (P80-03)"],
)


def attach_p80_collector_assistant_layer(app: FastAPI) -> None:
    app.include_router(p80_collector_assistant_v1_router)


@p80_collector_assistant_v1_router.post(
    "/scan",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_200_OK,
)
def v1_collector_scan(
    payload: P80CollectorScanRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = evaluate_collector_scan(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p80_collector_assistant_v1_router.post("/evaluate-price", response_model=ScanApiV1Envelope)
def v1_collector_evaluate_price(
    payload: P80CollectorPriceEvalRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = evaluate_collector_price(session, owner_user_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p80_collector_assistant_v1_router.get("/gaps", response_model=ScanApiV1Envelope)
def v1_collector_gaps(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_collector_gaps(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = P80CollectorGapListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p80_collector_assistant_v1_router.get("/opportunities", response_model=ScanApiV1Envelope)
def v1_collector_opportunities(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_collector_opportunities(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    body = P80CollectorOpportunityListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p80_collector_assistant_v1_router.get("/dashboard", response_model=ScanApiV1Envelope)
def v1_collector_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_collector_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
