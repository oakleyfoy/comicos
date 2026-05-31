from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.forecast_dashboard import get_forecast_detail, list_confidence, list_executions, list_forecasts, list_risks
from app.services.market_risk_agent import run_market_risk_agent
from app.services.price_forecast_agent import run_price_forecast_agent
from app.services.trend_forecast_agent import run_trend_forecast_agent

market_forecast_v1_router = APIRouter(prefix="/api/v1", tags=["Market Forecast API v1 (P47-02)"])


def attach_market_forecast_layer(app: FastAPI) -> None:
    app.include_router(market_forecast_v1_router)


@market_forecast_v1_router.get("/market-forecast/forecasts", response_model=ScanApiV1Envelope)
def v1_list_market_forecasts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_forecasts(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_forecast_v1_router.get("/market-forecast/forecasts/{forecast_id}", response_model=ScanApiV1Envelope)
def v1_get_market_forecast(
    forecast_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_forecast_detail(session, owner_user_id=int(current_user.id), forecast_id=forecast_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=forecast_id)


@market_forecast_v1_router.get("/market-forecast/risks", response_model=ScanApiV1Envelope)
def v1_list_market_risks(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_risks(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_forecast_v1_router.get("/market-forecast/confidence", response_model=ScanApiV1Envelope)
def v1_list_market_forecast_confidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_confidence(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_forecast_v1_router.post("/market-forecast/run/price", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_run_price_forecast_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_price_forecast_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_forecast_v1_router.post("/market-forecast/run/trends", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_run_trend_forecast_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_trend_forecast_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_forecast_v1_router.post("/market-forecast/run/risk", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_run_market_risk_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_market_risk_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_forecast_v1_router.get("/market-forecast/executions", response_model=ScanApiV1Envelope)
def v1_list_market_forecast_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_executions(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
