from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.market_intelligence_dashboard import (
    build_market_intelligence_dashboard,
    list_executions,
    list_observations,
    list_signals,
    list_snapshots,
    list_trends,
)
from app.services.market_observation_agent import generate_market_observations
from app.services.market_signal_agent import collect_market_signals
from app.services.market_snapshot_agent import run_snapshot_agent
from app.services.market_trend_agent import calculate_market_trends

market_intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Market Intelligence API v1 (P47-01)"])


def attach_market_intelligence_layer(app: FastAPI) -> None:
    app.include_router(market_intelligence_v1_router)


@market_intelligence_v1_router.get("/market-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_market_intelligence_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_market_intelligence_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@market_intelligence_v1_router.get("/market-intelligence/signals", response_model=ScanApiV1Envelope)
def v1_list_market_signals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_signals(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_intelligence_v1_router.get("/market-intelligence/snapshots", response_model=ScanApiV1Envelope)
def v1_list_market_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_snapshots(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_intelligence_v1_router.get("/market-intelligence/trends", response_model=ScanApiV1Envelope)
def v1_list_market_trends(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_trends(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_intelligence_v1_router.get("/market-intelligence/observations", response_model=ScanApiV1Envelope)
def v1_list_market_observations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_observations(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@market_intelligence_v1_router.post(
    "/market-intelligence/run/signals",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_market_signal_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = collect_market_signals(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_intelligence_v1_router.post(
    "/market-intelligence/run/snapshot",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_market_snapshot_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_snapshot_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_intelligence_v1_router.post(
    "/market-intelligence/run/trends",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_market_trend_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = calculate_market_trends(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_intelligence_v1_router.post(
    "/market-intelligence/run/observations",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_market_observation_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_market_observations(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@market_intelligence_v1_router.get("/market-intelligence/executions", response_model=ScanApiV1Envelope)
def v1_list_market_agent_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_executions(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
