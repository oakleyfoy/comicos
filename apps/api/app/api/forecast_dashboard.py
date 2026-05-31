from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.market_forecast import MarketForecastListResponse, MarketRiskAssessmentListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.forecast_dashboard import (
    build_forecast_dashboard,
    build_forecast_summary,
    list_highest_risk_assets,
    list_top_bearish_forecasts,
    list_top_bullish_forecasts,
)

forecast_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Forecast Dashboard API v1 (P47-02)"])


def attach_forecast_dashboard_layer(app: FastAPI) -> None:
    app.include_router(forecast_dashboard_v1_router)


@forecast_dashboard_v1_router.get("/forecast-dashboard", response_model=ScanApiV1Envelope)
def v1_forecast_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_forecast_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_dashboard_v1_router.get("/forecast-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_forecast_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_forecast_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_dashboard_v1_router.get("/forecast-dashboard/bullish", response_model=ScanApiV1Envelope)
def v1_forecast_dashboard_bullish(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = MarketForecastListResponse(
        items=list_top_bullish_forecasts(session, owner_user_id=int(current_user.id), limit=10),
        total_items=len(list_top_bullish_forecasts(session, owner_user_id=int(current_user.id), limit=1000)),
        limit=10,
        offset=0,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_dashboard_v1_router.get("/forecast-dashboard/bearish", response_model=ScanApiV1Envelope)
def v1_forecast_dashboard_bearish(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = MarketForecastListResponse(
        items=list_top_bearish_forecasts(session, owner_user_id=int(current_user.id), limit=10),
        total_items=len(list_top_bearish_forecasts(session, owner_user_id=int(current_user.id), limit=1000)),
        limit=10,
        offset=0,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_dashboard_v1_router.get("/forecast-dashboard/risk", response_model=ScanApiV1Envelope)
def v1_forecast_dashboard_risk(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = MarketRiskAssessmentListResponse(
        items=list_highest_risk_assets(session, owner_user_id=int(current_user.id), limit=10),
        total_items=len(list_highest_risk_assets(session, owner_user_id=int(current_user.id), limit=1000)),
        limit=10,
        offset=0,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
