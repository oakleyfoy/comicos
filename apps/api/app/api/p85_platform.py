"""P85 platform hardening APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p85_production_hardening import (
    P85CollectorHomeRead,
    P85PlatformCertificationRead,
    P85ProductionDashboardRead,
    P85WorkflowHealthRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.collector_home_service import build_collector_home
from app.services.platform_production_certification import build_production_dashboard, run_platform_production_certification
from app.services.workflow_health_service import build_workflow_health

p85_platform_router = APIRouter(tags=["Platform API v1 (P85)"])


def attach_p85_platform_layer(app: FastAPI) -> None:
    app.include_router(p85_platform_router)


@p85_platform_router.get("/api/v1/platform/certification", response_model=ScanApiV1Envelope)
def v1_platform_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P85PlatformCertificationRead = run_platform_production_certification(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p85_platform_router.get("/api/v1/platform/production-dashboard", response_model=ScanApiV1Envelope)
def v1_platform_production_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P85ProductionDashboardRead = build_production_dashboard(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p85_platform_router.get("/api/v1/platform/workflow-health", response_model=ScanApiV1Envelope)
def v1_platform_workflow_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P85WorkflowHealthRead = build_workflow_health(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p85_platform_router.get("/api/v1/collector-home", response_model=ScanApiV1Envelope)
def v1_collector_home(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P85CollectorHomeRead = build_collector_home(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
