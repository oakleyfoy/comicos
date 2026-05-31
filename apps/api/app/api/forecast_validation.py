from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.forecast_learning_agent import run_forecast_learning_agent
from app.services.forecast_reliability_agent import run_forecast_reliability_agent
from app.services.forecast_validation_agent import run_forecast_validation_agent
from app.services.forecast_validation_dashboard import (
    list_accuracy_metrics,
    list_drift_events,
    list_outcomes,
    list_signal_quality_metrics,
    list_validation_executions,
)

forecast_validation_v1_router = APIRouter(prefix="/api/v1", tags=["Forecast Validation API v1 (P47-04)"])


def attach_forecast_validation_layer(app: FastAPI) -> None:
    app.include_router(forecast_validation_v1_router)


@forecast_validation_v1_router.get("/forecast-validation/accuracy", response_model=ScanApiV1Envelope)
def v1_forecast_validation_accuracy(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_accuracy_metrics(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@forecast_validation_v1_router.get("/forecast-validation/drift", response_model=ScanApiV1Envelope)
def v1_forecast_validation_drift(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_drift_events(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@forecast_validation_v1_router.get("/forecast-validation/signal-quality", response_model=ScanApiV1Envelope)
def v1_forecast_validation_signal_quality(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_signal_quality_metrics(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@forecast_validation_v1_router.get("/forecast-validation/outcomes", response_model=ScanApiV1Envelope)
def v1_forecast_validation_outcomes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_outcomes(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@forecast_validation_v1_router.get("/forecast-validation/executions", response_model=ScanApiV1Envelope)
def v1_forecast_validation_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_validation_executions(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@forecast_validation_v1_router.post(
    "/forecast-validation/run/validation",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_forecast_validation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_forecast_validation_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@forecast_validation_v1_router.post(
    "/forecast-validation/run/learning",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_forecast_learning(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_forecast_learning_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)


@forecast_validation_v1_router.post(
    "/forecast-validation/run/reliability",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_forecast_reliability(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_forecast_reliability_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)
