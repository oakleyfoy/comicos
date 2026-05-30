"""Deterministic workflow registry and execution read routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.agent_workflow import WorkflowDefinitionCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.workflow_orchestrator import get_workflow_execution, list_workflow_executions
from app.services.workflow_registry import (
    create_workflow,
    disable_workflow,
    enable_workflow,
    get_workflow,
    list_workflows,
)

workflows_v1_router = APIRouter(prefix="/api/v1", tags=["Workflow Framework API v1"])


def attach_workflows_layer(app: FastAPI) -> None:
    app.include_router(workflows_v1_router)


@workflows_v1_router.get("/workflows", response_model=ScanApiV1Envelope)
def v1_list_workflows(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    enabled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_workflows(session, enabled=enabled, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@workflows_v1_router.get("/workflows/{workflow_id}", response_model=ScanApiV1Envelope)
def v1_get_workflow(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_workflow(session, workflow_id=workflow_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@workflows_v1_router.post("/workflows", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_workflow(
    payload: WorkflowDefinitionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_workflow(session, payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@workflows_v1_router.post("/workflows/{workflow_id}/enable", response_model=ScanApiV1Envelope)
def v1_enable_workflow(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = enable_workflow(session, workflow_id=workflow_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@workflows_v1_router.post("/workflows/{workflow_id}/disable", response_model=ScanApiV1Envelope)
def v1_disable_workflow(
    workflow_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = disable_workflow(session, workflow_id=workflow_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@workflows_v1_router.get("/workflow-executions", response_model=ScanApiV1Envelope)
def v1_list_workflow_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    workflow_id: int | None = Query(default=None),
    execution_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_workflow_executions(session, workflow_id=workflow_id, status=execution_status, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@workflows_v1_router.get("/workflow-executions/{execution_id}", response_model=ScanApiV1Envelope)
def v1_get_workflow_execution(
    execution_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_workflow_execution(session, workflow_execution_id=execution_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)
