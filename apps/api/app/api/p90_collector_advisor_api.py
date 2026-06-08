"""P90-03 Collector Advisor API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p90_collector_advisor import P90CollectorAdvisorDashboardRead, P90CollectorAdvisorHistoryRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.collector_advisor_service import (
    build_collector_advisor_dashboard,
    generate_collector_advisor_snapshot,
    list_advisor_history,
)

p90_collector_advisor_router = APIRouter(tags=["Collector Advisor (P90-03)"])


def attach_p90_collector_advisor_layer(app: FastAPI) -> None:
    app.include_router(p90_collector_advisor_router)


@p90_collector_advisor_router.get("/api/v1/collector-advisor", response_model=ScanApiV1Envelope)
def v1_collector_advisor_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90CollectorAdvisorDashboardRead = build_collector_advisor_dashboard(
        session, owner_user_id=int(current_user.id)
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_collector_advisor_router.get("/api/v1/collector-advisor/latest", response_model=ScanApiV1Envelope)
def v1_collector_advisor_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90CollectorAdvisorDashboardRead = build_collector_advisor_dashboard(
        session, owner_user_id=int(current_user.id)
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_collector_advisor_router.post("/api/v1/collector-advisor/generate", response_model=ScanApiV1Envelope)
def v1_collector_advisor_generate(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    generate_collector_advisor_snapshot(session, owner_user_id=owner_user_id, dry_run=False)
    session.commit()
    body: P90CollectorAdvisorDashboardRead = build_collector_advisor_dashboard(
        session, owner_user_id=owner_user_id
    )
    return wrap_object(body, owner_user_id=owner_user_id)


@p90_collector_advisor_router.get("/api/v1/collector-advisor/history", response_model=ScanApiV1Envelope)
def v1_collector_advisor_history(
    limit: int = Query(default=14, ge=1, le=90),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90CollectorAdvisorHistoryRead = list_advisor_history(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
