from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    AgentExecutionEvent,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
    WorkflowStepExecution,
)
from app.schemas.agent_workflow import (
    WorkflowExecutionDetail,
    WorkflowExecutionListResponse,
    WorkflowExecutionRead,
    WorkflowStepExecutionRead,
)
from app.services.agent_execution import (
    complete_execution,
    fail_execution,
    start_execution,
)
from app.services.agent_permissions import EXECUTE_PERMISSION_CAPABILITY, audit_permission_decision, check_permission
from app.services.agent_registry import get_agent
from app.services.workflow_events import (
    record_step_completed,
    record_step_failed,
    record_step_started,
    record_workflow_completed,
    record_workflow_failed,
    record_workflow_started,
)
from app.services.workflow_registry import clamp_workflow_pagination, get_workflow

WORKFLOW_STATUS_PENDING = "PENDING"
WORKFLOW_STATUS_RUNNING = "RUNNING"
WORKFLOW_STATUS_COMPLETED = "COMPLETED"
WORKFLOW_STATUS_FAILED = "FAILED"
WORKFLOW_STATUS_CANCELLED = "CANCELLED"

STEP_STATUS_PENDING = "PENDING"
STEP_STATUS_RUNNING = "RUNNING"
STEP_STATUS_COMPLETED = "COMPLETED"
STEP_STATUS_FAILED = "FAILED"
STEP_STATUS_CANCELLED = "CANCELLED"

_TERMINAL_WORKFLOW_STATUSES = {WORKFLOW_STATUS_COMPLETED, WORKFLOW_STATUS_FAILED, WORKFLOW_STATUS_CANCELLED}
_TERMINAL_STEP_STATUSES = {STEP_STATUS_COMPLETED, STEP_STATUS_FAILED, STEP_STATUS_CANCELLED}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return max(0, int((_as_utc(completed_at) - _as_utc(started_at)).total_seconds() * 1000))


def _workflow_execution_row(session: Session, *, workflow_execution_id: int) -> WorkflowExecution:
    row = session.get(WorkflowExecution, workflow_execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow execution not found.")
    return row


def _workflow_step_row(session: Session, *, workflow_step_id: int) -> WorkflowStep:
    row = session.get(WorkflowStep, workflow_step_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow step not found.")
    return row


def _workflow_step_execution_row(session: Session, *, workflow_step_execution_id: int) -> WorkflowStepExecution:
    row = session.get(WorkflowStepExecution, workflow_step_execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow step execution not found.")
    return row


def _workflow_step_rows(session: Session, *, workflow_id: int) -> list[WorkflowStep]:
    return session.exec(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order.asc(), WorkflowStep.id.asc())
    ).all()


def _workflow_step_execution_rows(session: Session, *, workflow_execution_id: int) -> list[WorkflowStepExecution]:
    return session.exec(
        select(WorkflowStepExecution)
        .where(WorkflowStepExecution.workflow_execution_id == workflow_execution_id)
        .order_by(WorkflowStepExecution.started_at.asc(), WorkflowStepExecution.id.asc())
    ).all()


def _workflow_execution_read(row: WorkflowExecution) -> WorkflowExecutionRead:
    return WorkflowExecutionRead(
        id=int(row.id or 0),
        workflow_id=row.workflow_id,
        execution_uuid=row.execution_uuid,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=row.duration_ms,
        triggered_by=row.triggered_by,
        trigger_source=row.trigger_source,
    )


def _workflow_step_execution_read(row: WorkflowStepExecution) -> WorkflowStepExecutionRead:
    return WorkflowStepExecutionRead(
        id=int(row.id or 0),
        workflow_execution_id=row.workflow_execution_id,
        workflow_step_id=row.workflow_step_id,
        agent_execution_id=row.agent_execution_id,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        duration_ms=row.duration_ms,
    )


def _detail(session: Session, workflow_execution: WorkflowExecution) -> WorkflowExecutionDetail:
    return WorkflowExecutionDetail(
        workflow=get_workflow(session, workflow_id=workflow_execution.workflow_id),
        execution=_workflow_execution_read(workflow_execution),
        step_executions=[
            _workflow_step_execution_read(step_execution)
            for step_execution in _workflow_step_execution_rows(session, workflow_execution_id=int(workflow_execution.id or 0))
        ],
    )


def _workflow_event_types(session: Session, *, workflow_execution_id: int) -> list[str]:
    rows = session.exec(
        select(AgentExecutionEvent.event_type)
        .join(WorkflowStepExecution, WorkflowStepExecution.agent_execution_id == AgentExecutionEvent.execution_id)
        .where(WorkflowStepExecution.workflow_execution_id == workflow_execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()
    return list(rows)


def _workflow_definition_row(session: Session, *, workflow_id: int) -> WorkflowDefinition:
    row = session.get(WorkflowDefinition, workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found.")
    return row


def _fail_workflow_guardrail(
    session: Session,
    *,
    workflow_execution: WorkflowExecution,
    reason: str,
) -> None:
    if workflow_execution.status in _TERMINAL_WORKFLOW_STATUSES:
        return
    failed_at = utc_now()
    workflow_execution.status = WORKFLOW_STATUS_FAILED
    workflow_execution.completed_at = failed_at
    workflow_execution.duration_ms = _duration_ms(workflow_execution.started_at, failed_at)
    session.add(workflow_execution)
    session.commit()
    session.refresh(workflow_execution)


def start_workflow(
    session: Session,
    *,
    workflow_id: int,
    triggered_by: str,
    trigger_source: str,
) -> WorkflowExecutionDetail:
    workflow = get_workflow(session, workflow_id=workflow_id)
    if not workflow.enabled:
        raise HTTPException(status_code=409, detail=f"Workflow {workflow.workflow_code} is disabled.")
    now = utc_now()
    row = WorkflowExecution(
        workflow_id=workflow_id,
        execution_uuid=str(uuid.uuid4()),
        status=WORKFLOW_STATUS_RUNNING,
        started_at=now,
        triggered_by=triggered_by.strip(),
        trigger_source=trigger_source.strip(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def execute_step(session: Session, *, workflow_execution_id: int) -> WorkflowExecutionDetail:
    workflow_execution = _workflow_execution_row(session, workflow_execution_id=workflow_execution_id)
    if workflow_execution.status != WORKFLOW_STATUS_RUNNING:
        raise HTTPException(status_code=409, detail="Workflow execution is not runnable.")
    workflow = get_workflow(session, workflow_id=workflow_execution.workflow_id)
    workflow_definition = _workflow_definition_row(session, workflow_id=workflow_execution.workflow_id)
    steps = _workflow_step_rows(session, workflow_id=workflow_execution.workflow_id)
    existing_rows = _workflow_step_execution_rows(session, workflow_execution_id=workflow_execution_id)
    existing_by_step_id = {row.workflow_step_id: row for row in existing_rows}
    running_step = next((row for row in existing_rows if row.status == STEP_STATUS_RUNNING), None)
    if running_step is not None:
        raise HTTPException(status_code=409, detail="A workflow step is already running.")

    next_step: WorkflowStep | None = None
    for step in steps:
        current_execution = existing_by_step_id.get(int(step.id or 0))
        if current_execution is None:
            next_step = step
            break
        if current_execution.status != STEP_STATUS_COMPLETED:
            raise HTTPException(status_code=409, detail="Previous workflow steps must complete before the next step can start.")
    if next_step is None:
        raise HTTPException(status_code=409, detail="Workflow execution has no remaining steps to execute.")
    audit_payload = {
        "workflow_id": workflow.id,
        "workflow_code": workflow.workflow_code,
        "workflow_execution_id": workflow_execution_id,
        "workflow_step_id": int(next_step.id or 0),
        "workflow_step_code": next_step.step_code,
        "triggered_by": workflow_execution.triggered_by,
    }
    if not workflow.enabled:
        audit_permission_decision(
            session,
            agent_id=next_step.agent_definition_id,
            execution_id=None,
            capability_code=EXECUTE_PERMISSION_CAPABILITY,
            action_code="workflow_step_execute",
            decision="denied",
            reason="workflow_disabled",
            event_payload_json={**audit_payload, "reason": "workflow_disabled"},
        )
        _fail_workflow_guardrail(
            session,
            workflow_execution=workflow_execution,
            reason="workflow_disabled",
        )
        raise HTTPException(status_code=409, detail=f"Workflow {workflow.workflow_code} is disabled.")
    step_agent = get_agent(session, agent_id=next_step.agent_definition_id)
    if not step_agent.enabled:
        audit_permission_decision(
            session,
            agent_id=step_agent.id,
            execution_id=None,
            capability_code=EXECUTE_PERMISSION_CAPABILITY,
            action_code="workflow_step_execute",
            decision="denied",
            reason="agent_disabled",
            event_payload_json={**audit_payload, "reason": "agent_disabled"},
        )
        _fail_workflow_guardrail(
            session,
            workflow_execution=workflow_execution,
            reason="agent_disabled",
        )
        raise HTTPException(status_code=409, detail=f"Agent {step_agent.code} is disabled.")
    execute_check = check_permission(
        session,
        agent_id=step_agent.id,
        capability_code=EXECUTE_PERMISSION_CAPABILITY,
        permission_scope="execute",
        action_code="workflow_step_execute",
        event_payload_json=audit_payload,
    )
    if not execute_check.allowed:
        _fail_workflow_guardrail(
            session,
            workflow_execution=workflow_execution,
            reason=execute_check.reason,
        )
        raise HTTPException(status_code=403, detail=f"Agent {step_agent.code} is missing execute permission.")
    for capability in sorted(step_agent.capabilities, key=lambda row: row.capability_code):
        if not capability.capability_code.endswith(".read"):
            continue
        read_check = check_permission(
            session,
            agent_id=step_agent.id,
            capability_code=capability.capability_code,
            permission_scope="read",
            action_code="workflow_step_execute",
            event_payload_json=audit_payload,
        )
        if not read_check.allowed:
            _fail_workflow_guardrail(
                session,
                workflow_execution=workflow_execution,
                reason=read_check.reason,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Agent {step_agent.code} is missing required read permission for {capability.capability_code}.",
            )

    agent_execution = start_execution(
        session,
        agent_id=next_step.agent_definition_id,
        triggered_by=workflow_execution.triggered_by,
        trigger_source=f"workflow:{workflow.workflow_code}",
        enforce_permissions=False,
    )
    now = utc_now()
    step_execution = WorkflowStepExecution(
        workflow_execution_id=workflow_execution_id,
        workflow_step_id=int(next_step.id or 0),
        agent_execution_id=agent_execution.execution.id,
        status=STEP_STATUS_RUNNING,
        started_at=now,
    )
    session.add(step_execution)
    session.flush()
    assert step_execution.id is not None
    if not existing_rows:
        record_workflow_started(
            session,
            agent_execution_id=agent_execution.execution.id,
            workflow=workflow_definition,
            workflow_execution=workflow_execution,
        )
    record_step_started(
        session,
        agent_execution_id=agent_execution.execution.id,
        workflow_step=next_step,
        workflow_step_execution=step_execution,
    )
    session.refresh(workflow_execution)
    return _detail(session, workflow_execution)


def complete_workflow(session: Session, *, workflow_execution_id: int) -> WorkflowExecutionDetail:
    workflow_execution = _workflow_execution_row(session, workflow_execution_id=workflow_execution_id)
    if workflow_execution.status in _TERMINAL_WORKFLOW_STATUSES:
        raise HTTPException(status_code=409, detail="Workflow execution is already terminal.")
    completed_at = utc_now()
    workflow_execution.status = WORKFLOW_STATUS_COMPLETED
    workflow_execution.completed_at = completed_at
    workflow_execution.duration_ms = _duration_ms(workflow_execution.started_at, completed_at)
    session.add(workflow_execution)
    session.commit()
    session.refresh(workflow_execution)
    return _detail(session, workflow_execution)


def fail_workflow(
    session: Session,
    *,
    workflow_execution_id: int,
    reason: str | None = None,
) -> WorkflowExecutionDetail:
    workflow_execution = _workflow_execution_row(session, workflow_execution_id=workflow_execution_id)
    if workflow_execution.status in _TERMINAL_WORKFLOW_STATUSES:
        raise HTTPException(status_code=409, detail="Workflow execution is already terminal.")
    failed_at = utc_now()
    workflow_execution.status = WORKFLOW_STATUS_FAILED
    workflow_execution.completed_at = failed_at
    workflow_execution.duration_ms = _duration_ms(workflow_execution.started_at, failed_at)
    session.add(workflow_execution)
    session.commit()
    session.refresh(workflow_execution)
    return _detail(session, workflow_execution)


def complete_step(
    session: Session,
    *,
    workflow_step_execution_id: int,
    event_payload_json: dict | None = None,
) -> WorkflowExecutionDetail:
    step_execution = _workflow_step_execution_row(session, workflow_step_execution_id=workflow_step_execution_id)
    if step_execution.status != STEP_STATUS_RUNNING:
        raise HTTPException(status_code=409, detail="Workflow step execution is not running.")
    step = _workflow_step_row(session, workflow_step_id=step_execution.workflow_step_id)
    workflow_execution = _workflow_execution_row(session, workflow_execution_id=step_execution.workflow_execution_id)
    completed_at = utc_now()
    step_execution.status = STEP_STATUS_COMPLETED
    step_execution.completed_at = completed_at
    step_execution.duration_ms = _duration_ms(step_execution.started_at, completed_at)
    session.add(step_execution)
    session.flush()
    record_step_completed(
        session,
        agent_execution_id=step_execution.agent_execution_id,
        workflow_step=step,
        workflow_step_execution=step_execution,
    )

    step_rows = _workflow_step_rows(session, workflow_id=workflow_execution.workflow_id)
    step_execution_rows = _workflow_step_execution_rows(session, workflow_execution_id=workflow_execution.id or 0)
    if len(step_execution_rows) == len(step_rows) and all(row.status == STEP_STATUS_COMPLETED for row in step_execution_rows):
        workflow_definition = _workflow_definition_row(session, workflow_id=workflow_execution.workflow_id)
        workflow_execution.status = WORKFLOW_STATUS_COMPLETED
        workflow_execution.completed_at = completed_at
        workflow_execution.duration_ms = _duration_ms(workflow_execution.started_at, completed_at)
        session.add(workflow_execution)
        record_workflow_completed(
            session,
            agent_execution_id=step_execution.agent_execution_id,
            workflow=workflow_definition,
            workflow_execution=workflow_execution,
        )
        complete_execution(
            session,
            execution_id=step_execution.agent_execution_id,
            event_payload_json=event_payload_json or {},
        )
        session.commit()
        session.refresh(workflow_execution)
        return _detail(session, workflow_execution)
    complete_execution(
        session,
        execution_id=step_execution.agent_execution_id,
        event_payload_json=event_payload_json or {},
    )
    session.refresh(workflow_execution)
    return _detail(session, workflow_execution)


def fail_step(
    session: Session,
    *,
    workflow_step_execution_id: int,
    reason: str | None = None,
) -> WorkflowExecutionDetail:
    step_execution = _workflow_step_execution_row(session, workflow_step_execution_id=workflow_step_execution_id)
    if step_execution.status != STEP_STATUS_RUNNING:
        raise HTTPException(status_code=409, detail="Workflow step execution is not running.")
    step = _workflow_step_row(session, workflow_step_id=step_execution.workflow_step_id)
    workflow_execution = _workflow_execution_row(session, workflow_execution_id=step_execution.workflow_execution_id)
    failed_at = utc_now()
    step_execution.status = STEP_STATUS_FAILED
    step_execution.completed_at = failed_at
    step_execution.duration_ms = _duration_ms(step_execution.started_at, failed_at)
    session.add(step_execution)
    session.flush()
    record_step_failed(
        session,
        agent_execution_id=step_execution.agent_execution_id,
        workflow_step=step,
        workflow_step_execution=step_execution,
        reason=reason,
    )
    workflow_definition = _workflow_definition_row(session, workflow_id=workflow_execution.workflow_id)
    workflow_execution.status = WORKFLOW_STATUS_FAILED
    workflow_execution.completed_at = failed_at
    workflow_execution.duration_ms = _duration_ms(workflow_execution.started_at, failed_at)
    session.add(workflow_execution)
    record_workflow_failed(
        session,
        agent_execution_id=step_execution.agent_execution_id,
        workflow=workflow_definition,
        workflow_execution=workflow_execution,
        reason=reason,
    )
    fail_execution(
        session,
        execution_id=step_execution.agent_execution_id,
        event_payload_json={"reason": reason} if reason is not None else {},
    )
    session.commit()
    session.refresh(workflow_execution)
    return _detail(session, workflow_execution)


def list_workflow_executions(
    session: Session,
    *,
    workflow_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowExecutionListResponse:
    limit, offset = clamp_workflow_pagination(limit=limit, offset=offset)
    filters = []
    if workflow_id is not None:
        filters.append(WorkflowExecution.workflow_id == workflow_id)
    if status is not None:
        filters.append(WorkflowExecution.status == status.strip().upper())
    total_items = int(session.exec(select(func.count()).select_from(WorkflowExecution).where(*filters)).one())
    rows = session.exec(
        select(WorkflowExecution)
        .where(*filters)
        .order_by(WorkflowExecution.started_at.asc(), WorkflowExecution.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return WorkflowExecutionListResponse(
        items=[_workflow_execution_read(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_workflow_execution(session: Session, *, workflow_execution_id: int) -> WorkflowExecutionDetail:
    return _detail(session, _workflow_execution_row(session, workflow_execution_id=workflow_execution_id))
