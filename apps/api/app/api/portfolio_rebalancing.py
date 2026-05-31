from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.portfolio_rebalancing import PortfolioRebalanceRecommendationListRead, PortfolioRebalanceSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.portfolio_rebalancing import (
    build_portfolio_rebalancing_summary,
    list_portfolio_rebalancing_recommendations,
    refresh_and_list_latest_portfolio_rebalancing,
)

portfolio_rebalancing_v1_router = APIRouter(prefix="/api/v1", tags=["Portfolio Rebalancing API v1 (P56-04)"])


def attach_portfolio_rebalancing_layer(app: FastAPI) -> None:
    app.include_router(portfolio_rebalancing_v1_router)


@portfolio_rebalancing_v1_router.get("/portfolio-rebalancing", response_model=ScanApiV1Envelope)
def v1_list_portfolio_rebalancing(
    rebalance_type: str | None = None,
    recommended_action: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_portfolio_rebalancing_recommendations(
        session,
        owner_user_id=int(current_user.id),
        rebalance_type=rebalance_type,
        recommended_action=recommended_action,
        priority_min=priority_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = PortfolioRebalanceRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@portfolio_rebalancing_v1_router.get("/portfolio-rebalancing/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_portfolio_rebalancing(
    rebalance_type: str | None = None,
    recommended_action: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_portfolio_rebalancing(
        session,
        owner_user_id=int(current_user.id),
        rebalance_type=rebalance_type,
        recommended_action=recommended_action,
        priority_min=priority_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = PortfolioRebalanceRecommendationListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@portfolio_rebalancing_v1_router.get("/portfolio-rebalancing/summary", response_model=ScanApiV1Envelope)
def v1_portfolio_rebalancing_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_portfolio_rebalancing_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
