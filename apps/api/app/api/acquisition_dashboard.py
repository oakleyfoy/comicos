from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.acquisition_dashboard import (
    AcquisitionDashboardActionsRead,
    AcquisitionDashboardRead,
    AcquisitionDashboardSummaryRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.acquisition_dashboard import (
    get_acquisition_dashboard,
    get_acquisition_dashboard_actions,
    get_acquisition_dashboard_summary,
)

acquisition_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Acquisition Dashboard API v1 (P55-05)"])


def attach_acquisition_dashboard_layer(app: FastAPI) -> None:
    app.include_router(acquisition_dashboard_v1_router)


@acquisition_dashboard_v1_router.get("/acquisition-dashboard", response_model=ScanApiV1Envelope)
def v1_acquisition_dashboard(
    publisher: str | None = None,
    priority: str | None = None,
    recommendation: str | None = None,
    source_type: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_acquisition_dashboard(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        priority=priority,
        recommendation=recommendation,
        source_type=source_type,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@acquisition_dashboard_v1_router.get("/acquisition-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_acquisition_dashboard_summary(
    publisher: str | None = None,
    priority: str | None = None,
    recommendation: str | None = None,
    source_type: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_acquisition_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        priority=priority,
        recommendation=recommendation,
        source_type=source_type,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@acquisition_dashboard_v1_router.get("/acquisition-dashboard/actions", response_model=ScanApiV1Envelope)
def v1_acquisition_dashboard_actions(
    publisher: str | None = None,
    priority: str | None = None,
    recommendation: str | None = None,
    source_type: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_acquisition_dashboard_actions(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        priority=priority,
        recommendation=recommendation,
        source_type=source_type,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
