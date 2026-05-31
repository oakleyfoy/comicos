from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.executive_dashboard import ExecutiveDashboardRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.executive_dashboard import (
    get_executive_dashboard,
    get_executive_dashboard_actions,
    get_executive_dashboard_summary,
)

executive_dashboard_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Executive Dashboard API v1 (P57-04)"],
)


def attach_executive_dashboard_layer(app: FastAPI) -> None:
    app.include_router(executive_dashboard_v1_router)


def _filter_kwargs(
    *,
    section: str | None,
    recommendation_type: str | None,
    action_type: str | None,
    priority_min: float | None,
    publisher: str | None,
) -> dict:
    return {
        "section": section.strip().upper() if section and section.strip() else None,
        "recommendation_type": recommendation_type.strip().upper() if recommendation_type and recommendation_type.strip() else None,
        "action_type": action_type.strip().upper() if action_type and action_type.strip() else None,
        "priority_min": priority_min,
        "publisher": publisher,
    }


@executive_dashboard_v1_router.get("/executive-dashboard", response_model=ScanApiV1Envelope)
def v1_executive_dashboard(
    section: str | None = None,
    recommendation_type: str | None = None,
    action_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_executive_dashboard(
        session,
        owner_user_id=int(current_user.id),
        **_filter_kwargs(
            section=section,
            recommendation_type=recommendation_type,
            action_type=action_type,
            priority_min=priority_min,
            publisher=publisher,
        ),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@executive_dashboard_v1_router.get("/executive-dashboard/summary", response_model=ScanApiV1Envelope)
def v1_executive_dashboard_summary(
    section: str | None = None,
    recommendation_type: str | None = None,
    action_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_executive_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
        **_filter_kwargs(
            section=section,
            recommendation_type=recommendation_type,
            action_type=action_type,
            priority_min=priority_min,
            publisher=publisher,
        ),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@executive_dashboard_v1_router.get("/executive-dashboard/actions", response_model=ScanApiV1Envelope)
def v1_executive_dashboard_actions(
    section: str | None = None,
    recommendation_type: str | None = None,
    action_type: str | None = None,
    priority_min: float | None = Query(default=None, ge=0.0, le=100.0),
    publisher: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_executive_dashboard_actions(
        session,
        owner_user_id=int(current_user.id),
        **_filter_kwargs(
            section=section,
            recommendation_type=recommendation_type,
            action_type=action_type,
            priority_min=priority_min,
            publisher=publisher,
        ),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
