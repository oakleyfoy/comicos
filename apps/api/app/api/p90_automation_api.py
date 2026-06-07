"""P90 Automation & Alerts API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p90_automation import (
    P90AutomationDashboardRead,
    P90AutomationSummaryRead,
    P90CollectorAlertListResponse,
    P90CollectorAlertRead,
    P90CollectorAlertUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.collector_alert_service import (
    build_automation_dashboard,
    build_automation_summary,
    list_collector_alerts,
    update_collector_alert,
)

p90_automation_router = APIRouter(tags=["Automation & Alerts (P90-01)"])


def attach_p90_automation_layer(app: FastAPI) -> None:
    app.include_router(p90_automation_router)


@p90_automation_router.get("/api/v1/automation/alerts", response_model=ScanApiV1Envelope)
def v1_automation_alerts(
    alert_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90CollectorAlertListResponse = list_collector_alerts(
        session,
        owner_user_id=int(current_user.id),
        alert_type=alert_type,
        status=status,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_automation_router.get("/api/v1/automation/summary", response_model=ScanApiV1Envelope)
def v1_automation_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90AutomationSummaryRead = build_automation_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_automation_router.get("/api/v1/automation/dashboard", response_model=ScanApiV1Envelope)
def v1_automation_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90AutomationDashboardRead = build_automation_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_automation_router.patch("/api/v1/automation/alerts/{alert_id}", response_model=ScanApiV1Envelope)
def v1_automation_alert_patch(
    alert_id: int,
    payload: P90CollectorAlertUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90CollectorAlertRead = update_collector_alert(
        session,
        owner_user_id=int(current_user.id),
        alert_id=alert_id,
        payload=payload,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))
