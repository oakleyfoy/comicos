from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.agent_analytics import (
    generate_snapshot,
    get_latest_snapshot,
    get_snapshot_detail,
    list_agent_metrics,
    list_recommendation_outcome_metrics,
    list_snapshots,
    list_workflow_metrics,
)

agent_analytics_v1_router = APIRouter(prefix="/api/v1", tags=["Agent Analytics API v1 (P45-07)"])


def attach_agent_analytics_layer(app: FastAPI) -> None:
    app.include_router(agent_analytics_v1_router)


@agent_analytics_v1_router.get("/agent-analytics", response_model=ScanApiV1Envelope)
def v1_get_agent_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_snapshot(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@agent_analytics_v1_router.get("/agent-analytics/snapshots", response_model=ScanApiV1Envelope)
def v1_list_agent_analytics_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_snapshots(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_analytics_v1_router.get("/agent-analytics/snapshots/{snapshot_id}", response_model=ScanApiV1Envelope)
def v1_get_agent_analytics_snapshot_detail(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_snapshot_detail(session, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)


@agent_analytics_v1_router.post(
    "/agent-analytics/generate",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_generate_agent_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_snapshot(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot.id)


@agent_analytics_v1_router.get("/agent-analytics/agents", response_model=ScanApiV1Envelope)
def v1_list_agent_analytics_agents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_agent_metrics(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_analytics_v1_router.get("/agent-analytics/workflows", response_model=ScanApiV1Envelope)
def v1_list_agent_analytics_workflows(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_workflow_metrics(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agent_analytics_v1_router.get("/agent-analytics/recommendations", response_model=ScanApiV1Envelope)
def v1_list_agent_analytics_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_recommendation_outcome_metrics(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
