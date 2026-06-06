from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.foc_dashboard import FocDashboardListResponse, FocDashboardRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.foc_dashboard import get_foc_dashboard_summary, list_foc_dashboard_actions, list_foc_dashboard_releases
from app.services.nav_route_safe_get import safe_foc_dashboard

foc_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["FOC Action Dashboard API v1 (P52-03)"])


def attach_foc_dashboard_layer(app: FastAPI) -> None:
    app.include_router(foc_dashboard_v1_router)


def _filter_params(
    decision_type: str | None,
    publisher: str | None,
    max_days_until_foc: int | None,
    max_days_until_release: int | None,
) -> dict:
    return {
        "decision_type": decision_type,
        "publisher": publisher,
        "max_days_until_foc": max_days_until_foc,
        "max_days_until_release": max_days_until_release,
    }


@foc_dashboard_v1_router.get("/foc-dashboard", response_model=ScanApiV1Envelope)
def v1_foc_dashboard(
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = Query(None, ge=0, le=365),
    max_days_until_release: int | None = Query(None, ge=0, le=365),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = safe_foc_dashboard(
        session,
        owner_user_id=int(current_user.id),
        **_filter_params(decision_type, publisher, max_days_until_foc, max_days_until_release),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@foc_dashboard_v1_router.get("/foc-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_foc_dashboard_summary(
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = Query(None, ge=0, le=365),
    max_days_until_release: int | None = Query(None, ge=0, le=365),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_foc_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
        **_filter_params(decision_type, publisher, max_days_until_foc, max_days_until_release),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@foc_dashboard_v1_router.get("/foc-dashboard/actions", response_model=ScanApiV1Envelope)
def v1_foc_dashboard_actions(
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_foc: int | None = Query(None, ge=0, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_foc_dashboard_actions(
        session,
        owner_user_id=int(current_user.id),
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_foc=max_days_until_foc,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@foc_dashboard_v1_router.get("/foc-dashboard/releases", response_model=ScanApiV1Envelope)
def v1_foc_dashboard_releases(
    decision_type: str | None = None,
    publisher: str | None = None,
    max_days_until_release: int | None = Query(None, ge=0, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_foc_dashboard_releases(
        session,
        owner_user_id=int(current_user.id),
        decision_type=decision_type,
        publisher=publisher,
        max_days_until_release=max_days_until_release,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
