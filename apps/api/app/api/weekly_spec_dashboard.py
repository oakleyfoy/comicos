from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.schemas.weekly_spec_dashboard import WeeklySpecDashboardRead, WeeklySpecDashboardSummaryRead
from app.services.weekly_spec_dashboard import build_weekly_spec_dashboard, build_weekly_spec_dashboard_summary

weekly_spec_dashboard_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Weekly Spec Dashboard API v1 (P60-05)"],
)


def attach_weekly_spec_dashboard_layer(app: FastAPI) -> None:
    app.include_router(weekly_spec_dashboard_v1_router)


@weekly_spec_dashboard_v1_router.get("/weekly-spec-dashboard", response_model=ScanApiV1Envelope)
def v1_weekly_spec_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_weekly_spec_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@weekly_spec_dashboard_v1_router.get("/weekly-spec-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_weekly_spec_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_weekly_spec_dashboard_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
