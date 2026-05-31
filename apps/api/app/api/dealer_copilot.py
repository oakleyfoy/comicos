from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.dealer_copilot_engine import (
    REVIEW_STATUS_ACCEPTED,
    REVIEW_STATUS_DISMISSED,
    REVIEW_STATUS_REVIEWED,
    append_review,
    build_copilot_dashboard,
    generate_recommendations,
    get_recommendation_for_owner,
    list_executions,
    list_opportunities,
    list_recommendations,
)

dealer_copilot_v1_router = APIRouter(prefix="/api/v1", tags=["Dealer Copilot API v1 (P47-03)"])


def attach_dealer_copilot_layer(app: FastAPI) -> None:
    app.include_router(dealer_copilot_v1_router)


@dealer_copilot_v1_router.get("/dealer-copilot/recommendations", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_recommendations(
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
        recommendation_status=recommendation_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@dealer_copilot_v1_router.get("/dealer-copilot/recommendations/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_recommendation_detail(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recommendation_for_owner(session, owner_user_id=int(current_user.id), recommendation_id=recommendation_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=recommendation_id)


@dealer_copilot_v1_router.get("/dealer-copilot/opportunities", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_opportunities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_opportunities(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


def _top_type_response(session: Session, *, owner_user_id: int, recommendation_type: str, limit: int) -> ScanApiV1Envelope:
    body = list_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation_type=recommendation_type,
        limit=limit,
        offset=0,
    )
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@dealer_copilot_v1_router.get("/dealer-copilot/top-buys", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_top_buys(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _top_type_response(session, owner_user_id=int(current_user.id), recommendation_type="BUY", limit=limit)


@dealer_copilot_v1_router.get("/dealer-copilot/top-sells", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_top_sells(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _top_type_response(session, owner_user_id=int(current_user.id), recommendation_type="SELL", limit=limit)


@dealer_copilot_v1_router.get("/dealer-copilot/top-holds", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_top_holds(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _top_type_response(session, owner_user_id=int(current_user.id), recommendation_type="HOLD", limit=limit)


@dealer_copilot_v1_router.get("/dealer-copilot/top-grades", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_top_grades(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _top_type_response(session, owner_user_id=int(current_user.id), recommendation_type="GRADE", limit=limit)


@dealer_copilot_v1_router.get("/dealer-copilot/top-watchlist", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_top_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _top_type_response(session, owner_user_id=int(current_user.id), recommendation_type="WATCH", limit=limit)


@dealer_copilot_v1_router.get("/dealer-copilot/executions", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_executions(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@dealer_copilot_v1_router.get("/dealer-copilot/dashboard", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_copilot_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@dealer_copilot_v1_router.post("/dealer-copilot/run", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_run_dealer_copilot(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_recommendations(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


def _review_response(session: Session, *, owner_user_id: int, recommendation_id: int, reviewed_by: str, review_status: str) -> ScanApiV1Envelope:
    body = append_review(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        reviewed_by=reviewed_by,
        review_status=review_status,
    )
    return wrap_object(body, owner_user_id=owner_user_id, snapshot_id=recommendation_id)


@dealer_copilot_v1_router.post("/dealer-copilot/recommendations/{recommendation_id}/reviewed", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_reviewed(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _review_response(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
        review_status=REVIEW_STATUS_REVIEWED,
    )


@dealer_copilot_v1_router.post("/dealer-copilot/recommendations/{recommendation_id}/dismissed", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_dismissed(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _review_response(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
        review_status=REVIEW_STATUS_DISMISSED,
    )


@dealer_copilot_v1_router.post("/dealer-copilot/recommendations/{recommendation_id}/accepted", response_model=ScanApiV1Envelope)
def v1_dealer_copilot_accepted(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return _review_response(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
        review_status=REVIEW_STATUS_ACCEPTED,
    )
