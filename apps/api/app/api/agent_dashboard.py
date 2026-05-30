"""Operational visibility routes for agent, workflow, and recommendation activity."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.agent_dashboard import AgentDashboardHealthRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.agent_dashboard import (
    get_agent_status_summary,
    get_dashboard_summary,
    get_recent_executions,
    get_recent_recommendations,
    get_recommendation_review_queue,
    get_workflow_status_summary,
)

agent_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Agent Dashboard API v1"])


def attach_agent_dashboard_layer(app: FastAPI) -> None:
    app.include_router(agent_dashboard_v1_router)


@agent_dashboard_v1_router.get("/agent-dashboard", response_model=ScanApiV1Envelope)
def v1_get_agent_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_dashboard_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@agent_dashboard_v1_router.get("/agent-dashboard/agents", response_model=ScanApiV1Envelope)
def v1_get_agent_dashboard_agents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_agent_status_summary(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_dashboard_v1_router.get("/agent-dashboard/workflows", response_model=ScanApiV1Envelope)
def v1_get_agent_dashboard_workflows(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_workflow_status_summary(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_dashboard_v1_router.get("/agent-dashboard/executions", response_model=ScanApiV1Envelope)
def v1_get_agent_dashboard_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    agent_code: str | None = Query(default=None),
    workflow_code: str | None = Query(default=None),
    execution_status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recent_executions(
        session,
        owner_user_id=int(current_user.id),
        agent_code=agent_code,
        workflow_code=workflow_code,
        status=execution_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_dashboard_v1_router.get("/agent-dashboard/recommendations", response_model=ScanApiV1Envelope)
def v1_get_agent_dashboard_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_type: str | None = Query(default=None),
    recommendation_status: str | None = Query(default=None),
    queue_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if queue_only:
        body = get_recommendation_review_queue(
            session,
            owner_user_id=int(current_user.id),
            limit=limit,
            offset=offset,
        )
    else:
        body = get_recent_recommendations(
            session,
            owner_user_id=int(current_user.id),
            recommendation_type=recommendation_type,
            status=recommendation_status,
            limit=limit,
            offset=offset,
        )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_dashboard_v1_router.get("/agent-dashboard/health", response_model=ScanApiV1Envelope)
def v1_get_agent_dashboard_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = AgentDashboardHealthRead(
        agents=get_agent_status_summary(session, owner_user_id=int(current_user.id), limit=200, offset=0).items,
        workflows=get_workflow_status_summary(session, owner_user_id=int(current_user.id), limit=200, offset=0).items,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
