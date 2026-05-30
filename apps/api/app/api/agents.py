"""Foundational deterministic agent registry and execution routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.agent import AgentDefinitionCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.agent_execution import get_execution, list_executions
from app.services.agent_registry import disable_agent, enable_agent, get_agent, list_agents, register_agent

agents_v1_router = APIRouter(prefix="/api/v1", tags=["Agent Framework API v1"])


def attach_agents_layer(app: FastAPI) -> None:
    app.include_router(agents_v1_router)


@agents_v1_router.get("/agents", response_model=ScanApiV1Envelope)
def v1_list_agents(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_agents(session, enabled=enabled, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agents_v1_router.get("/agents/{agent_id}", response_model=ScanApiV1Envelope)
def v1_get_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_agent(session, agent_id=agent_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@agents_v1_router.post("/agents", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_register_agent(
    payload: AgentDefinitionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = register_agent(session, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@agents_v1_router.post("/agents/{agent_id}/enable", response_model=ScanApiV1Envelope)
def v1_enable_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = enable_agent(session, agent_id=agent_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@agents_v1_router.post("/agents/{agent_id}/disable", response_model=ScanApiV1Envelope)
def v1_disable_agent(
    agent_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = disable_agent(session, agent_id=agent_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@agents_v1_router.get("/agent-executions", response_model=ScanApiV1Envelope)
def v1_list_agent_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    agent_id: int | None = Query(default=None),
    execution_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_executions(session, agent_id=agent_id, status=execution_status, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@agents_v1_router.get("/agent-executions/{execution_id}", response_model=ScanApiV1Envelope)
def v1_get_agent_execution(
    execution_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_execution(session, execution_id=execution_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)
