from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.forecast_validation_dashboard import (
    build_forecast_validation_dashboard,
    build_validation_summary,
    list_accuracy_metrics,
    list_drift_events,
    list_outcomes,
    list_signal_quality_metrics,
)

forecast_validation_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Forecast Validation Dashboard API v1 (P47-04)"])


def attach_forecast_validation_dashboard_layer(app: FastAPI) -> None:
    app.include_router(forecast_validation_dashboard_v1_router)


@forecast_validation_dashboard_v1_router.get("/forecast-validation-dashboard", response_model=ScanApiV1Envelope)
def v1_forecast_validation_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_forecast_validation_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_validation_dashboard_v1_router.get("/forecast-validation-dashboard/accuracy", response_model=ScanApiV1Envelope)
def v1_forecast_validation_dashboard_accuracy(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_accuracy_metrics(session, owner_user_id=int(current_user.id), limit=10, offset=0)
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_validation_dashboard_v1_router.get("/forecast-validation-dashboard/drift", response_model=ScanApiV1Envelope)
def v1_forecast_validation_dashboard_drift(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_drift_events(session, owner_user_id=int(current_user.id), limit=10, offset=0)
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_validation_dashboard_v1_router.get("/forecast-validation-dashboard/signal-quality", response_model=ScanApiV1Envelope)
def v1_forecast_validation_dashboard_signal_quality(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_signal_quality_metrics(session, owner_user_id=int(current_user.id), limit=10, offset=0)
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_validation_dashboard_v1_router.get("/forecast-validation-dashboard/outcomes", response_model=ScanApiV1Envelope)
def v1_forecast_validation_dashboard_outcomes(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_outcomes(session, owner_user_id=int(current_user.id), limit=10, offset=0)
    return wrap_object(body, owner_user_id=int(current_user.id))


@forecast_validation_dashboard_v1_router.get("/forecast-validation-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_forecast_validation_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_validation_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
