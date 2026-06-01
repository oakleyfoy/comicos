from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.future_release_dashboard import FutureReleaseDashboardRead, FutureReleaseDashboardSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.future_release_dashboard import (
    build_future_release_dashboard,
    build_future_release_dashboard_summary,
)

future_release_dashboard_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Future Release Dashboard API v1 (P58-05)"],
)


def attach_future_release_dashboard_layer(app: FastAPI) -> None:
    app.include_router(future_release_dashboard_v1_router)


@future_release_dashboard_v1_router.get("/future-release-dashboard", response_model=ScanApiV1Envelope)
def v1_future_release_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_future_release_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@future_release_dashboard_v1_router.get("/future-release-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_future_release_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_future_release_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
        refresh=True,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
