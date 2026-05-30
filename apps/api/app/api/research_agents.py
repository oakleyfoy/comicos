"""Read-only research agent routes backed by agent execution records."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.agent_results import (
    get_finding,
    get_snapshot_detail_for_owner,
    list_findings,
    list_snapshots,
    mark_finding_dismissed,
    mark_finding_reviewed,
)
from app.services.marketplace_research_agent import run_marketplace_research_agent
from app.services.new_release_research_agent import run_new_release_research_agent

research_agents_v1_router = APIRouter(prefix="/api/v1", tags=["Research Agents API v1"])


def attach_research_agents_layer(app: FastAPI) -> None:
    app.include_router(research_agents_v1_router)


@research_agents_v1_router.get("/research-snapshots", response_model=ScanApiV1Envelope)
def v1_list_research_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    agent_code: str | None = Query(default=None),
    research_type: str | None = Query(default=None),
    snapshot_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_snapshots(
        session,
        owner_user_id=int(current_user.id),
        agent_code=agent_code,
        research_type=research_type,
        status=snapshot_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@research_agents_v1_router.get("/research-snapshots/{snapshot_id}", response_model=ScanApiV1Envelope)
def v1_get_research_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_snapshot_detail_for_owner(session, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot.id)


@research_agents_v1_router.get("/research-findings", response_model=ScanApiV1Envelope)
def v1_list_research_findings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None),
    finding_type: str | None = Query(default=None),
    finding_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_findings(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        finding_type=finding_type,
        status=finding_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@research_agents_v1_router.get("/research-findings/{finding_id}", response_model=ScanApiV1Envelope)
def v1_get_research_finding(
    finding_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_finding(session, owner_user_id=int(current_user.id), finding_id=finding_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot_id)


@research_agents_v1_router.post("/research-findings/{finding_id}/reviewed", response_model=ScanApiV1Envelope)
def v1_mark_research_finding_reviewed(
    finding_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_finding_reviewed(session, owner_user_id=int(current_user.id), finding_id=finding_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot_id)


@research_agents_v1_router.post("/research-findings/{finding_id}/dismissed", response_model=ScanApiV1Envelope)
def v1_mark_research_finding_dismissed(
    finding_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = mark_finding_dismissed(session, owner_user_id=int(current_user.id), finding_id=finding_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot_id)


@research_agents_v1_router.post(
    "/research-agents/marketplace/run",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_marketplace_research_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_marketplace_research_agent(session, current_user=current_user)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot.id)


@research_agents_v1_router.post(
    "/research-agents/new-releases/run",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_new_release_research_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_new_release_research_agent(session, current_user=current_user)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.snapshot.id)
