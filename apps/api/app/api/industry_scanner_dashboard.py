from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.industry_scanner_dashboard import IndustryScannerDashboardRead, IndustryScannerDashboardSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.industry_scanner_dashboard import (
    build_industry_scanner_dashboard,
    build_industry_scanner_dashboard_summary,
)

industry_scanner_dashboard_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Industry Scanner Dashboard API v1 (P59-05)"],
)


def attach_industry_scanner_dashboard_layer(app: FastAPI) -> None:
    app.include_router(industry_scanner_dashboard_v1_router)


@industry_scanner_dashboard_v1_router.get("/industry-scanner-dashboard", response_model=ScanApiV1Envelope)
def v1_industry_scanner_dashboard(
    refresh: bool = Query(default=True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_industry_scanner_dashboard(
        session,
        owner_user_id=int(current_user.id),
        refresh=refresh,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@industry_scanner_dashboard_v1_router.get("/industry-scanner-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_industry_scanner_dashboard_summary(
    refresh: bool = Query(default=True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_industry_scanner_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
        refresh=refresh,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
