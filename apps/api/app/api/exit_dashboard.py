from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.exit_dashboard import ExitDashboardActionsRead, ExitDashboardRead, ExitDashboardSummaryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.exit_dashboard import get_exit_dashboard, get_exit_dashboard_actions, get_exit_dashboard_summary

exit_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Exit Dashboard API v1 (P56-05)"])


def attach_exit_dashboard_layer(app: FastAPI) -> None:
    app.include_router(exit_dashboard_v1_router)


@exit_dashboard_v1_router.get("/exit-dashboard", response_model=ScanApiV1Envelope)
def v1_exit_dashboard(
    publisher: str | None = None,
    recommendation: str | None = None,
    action: str | None = None,
    score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_exit_dashboard(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        recommendation=recommendation,
        action=action,
        score_min=score_min,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@exit_dashboard_v1_router.get("/exit-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_exit_dashboard_summary(
    publisher: str | None = None,
    recommendation: str | None = None,
    action: str | None = None,
    score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_exit_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        recommendation=recommendation,
        action=action,
        score_min=score_min,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@exit_dashboard_v1_router.get("/exit-dashboard/actions", response_model=ScanApiV1Envelope)
def v1_exit_dashboard_actions(
    publisher: str | None = None,
    recommendation: str | None = None,
    action: str | None = None,
    score_min: float | None = Query(default=None, ge=0.0, le=100.0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_exit_dashboard_actions(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        recommendation=recommendation,
        action=action,
        score_min=score_min,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
