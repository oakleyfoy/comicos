from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import AgentDefinition, WorkflowDefinition, WorkflowExecution, WorkflowStep
from app.schemas.agent_workflow import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionRead,
    WorkflowStepCreate,
    WorkflowStepRead,
)
from app.services.workflow_scheduler import normalize_schedule_fields


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_workflow_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _get_workflow_row(session: Session, *, workflow_id: int) -> WorkflowDefinition:
    row = session.get(WorkflowDefinition, workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow definition not found.")
    return row


def _workflow_by_code(session: Session, *, workflow_code: str) -> WorkflowDefinition | None:
    return session.exec(select(WorkflowDefinition).where(WorkflowDefinition.workflow_code == workflow_code)).first()


def _workflow_has_execution_history(session: Session, *, workflow_id: int) -> bool:
    count = int(
        session.exec(
            select(func.count()).select_from(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
        ).one()
    )
    return count > 0


def _ensure_agent_exists(session: Session, *, agent_definition_id: int) -> AgentDefinition:
    row = session.get(AgentDefinition, agent_definition_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Referenced agent definition not found.")
    return row


def _normalize_steps(session: Session, *, steps: list[WorkflowStepCreate]) -> list[WorkflowStepCreate]:
    if not steps:
        raise HTTPException(status_code=422, detail="A workflow must contain at least one step.")
    normalized: dict[int, WorkflowStepCreate] = {}
    step_codes: set[str] = set()
    for step in steps:
        _ensure_agent_exists(session, agent_definition_id=step.agent_definition_id)
        step_code = step.step_code.strip().lower()
        if step.step_order in normalized:
            raise HTTPException(status_code=409, detail=f"Duplicate workflow step order {step.step_order}.")
        if step_code in step_codes:
            raise HTTPException(status_code=409, detail=f"Duplicate workflow step code {step_code}.")
        normalized[step.step_order] = WorkflowStepCreate(
            step_order=step.step_order,
            agent_definition_id=step.agent_definition_id,
            step_name=step.step_name.strip(),
            step_code=step_code,
            required_success=step.required_success,
            timeout_seconds=step.timeout_seconds,
        )
        step_codes.add(step_code)
    expected_orders = list(range(1, len(normalized) + 1))
    actual_orders = sorted(normalized.keys())
    if actual_orders != expected_orders:
        raise HTTPException(status_code=409, detail="Workflow step ordering must start at 1 and be contiguous.")
    return [normalized[key] for key in actual_orders]


def _list_step_rows(session: Session, *, workflow_id: int) -> list[WorkflowStep]:
    return session.exec(
        select(WorkflowStep)
        .where(WorkflowStep.workflow_id == workflow_id)
        .order_by(WorkflowStep.step_order.asc(), WorkflowStep.id.asc())
    ).all()


def _replace_steps(session: Session, *, workflow_id: int, steps: list[WorkflowStepCreate]) -> None:
    existing_rows = _list_step_rows(session, workflow_id=workflow_id)
    for row in existing_rows:
        session.delete(row)
    if existing_rows:
        session.flush()
    for step in _normalize_steps(session, steps=steps):
        session.add(
            WorkflowStep(
                workflow_id=workflow_id,
                step_order=step.step_order,
                agent_definition_id=step.agent_definition_id,
                step_name=step.step_name,
                step_code=step.step_code,
                required_success=step.required_success,
                timeout_seconds=step.timeout_seconds,
            )
        )
    session.flush()


def _step_read(row: WorkflowStep) -> WorkflowStepRead:
    return WorkflowStepRead(
        id=int(row.id or 0),
        workflow_id=row.workflow_id,
        step_order=row.step_order,
        agent_definition_id=row.agent_definition_id,
        step_name=row.step_name,
        step_code=row.step_code,
        required_success=row.required_success,
        timeout_seconds=row.timeout_seconds,
    )


def _workflow_read(session: Session, row: WorkflowDefinition) -> WorkflowDefinitionRead:
    return WorkflowDefinitionRead(
        id=int(row.id or 0),
        workflow_code=row.workflow_code,
        workflow_name=row.workflow_name,
        description=row.description,
        enabled=row.enabled,
        schedule_enabled=row.schedule_enabled,
        cron_expression=row.cron_expression,
        next_run_at=row.next_run_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        steps=[_step_read(step) for step in _list_step_rows(session, workflow_id=int(row.id or 0))],
    )


def create_workflow(session: Session, *, payload: WorkflowDefinitionCreate) -> WorkflowDefinitionRead:
    workflow_code = payload.workflow_code.strip().lower()
    if _workflow_by_code(session, workflow_code=workflow_code) is not None:
        raise HTTPException(status_code=409, detail=f"Workflow code {workflow_code} is already registered.")
    schedule_enabled, cron_expression, next_run_at = normalize_schedule_fields(
        schedule_enabled=payload.schedule_enabled,
        cron_expression=payload.cron_expression,
        next_run_at=payload.next_run_at,
    )
    now = utc_now()
    row = WorkflowDefinition(
        workflow_code=workflow_code,
        workflow_name=payload.workflow_name.strip(),
        description=payload.description.strip(),
        enabled=payload.enabled,
        schedule_enabled=schedule_enabled,
        cron_expression=cron_expression,
        next_run_at=next_run_at,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    _replace_steps(session, workflow_id=int(row.id), steps=payload.steps)
    session.commit()
    session.refresh(row)
    return _workflow_read(session, row)


def update_workflow(
    session: Session,
    *,
    workflow_id: int,
    workflow_name: str | None = None,
    description: str | None = None,
    schedule_enabled: bool | None = None,
    cron_expression: str | None = None,
    next_run_at: datetime | None = None,
    steps: list[WorkflowStepCreate] | None = None,
) -> WorkflowDefinitionRead:
    row = _get_workflow_row(session, workflow_id=workflow_id)
    requested_mutation = any(
        value is not None for value in (workflow_name, description, schedule_enabled, cron_expression, next_run_at, steps)
    )
    if requested_mutation and _workflow_has_execution_history(session, workflow_id=workflow_id):
        raise HTTPException(status_code=409, detail="Workflow definitions are immutable after execution history exists.")
    if workflow_name is not None:
        row.workflow_name = workflow_name.strip()
    if description is not None:
        row.description = description.strip()
    if schedule_enabled is not None or cron_expression is not None or next_run_at is not None:
        normalized_schedule_enabled, normalized_cron_expression, normalized_next_run_at = normalize_schedule_fields(
            schedule_enabled=row.schedule_enabled if schedule_enabled is None else schedule_enabled,
            cron_expression=row.cron_expression if cron_expression is None else cron_expression,
            next_run_at=row.next_run_at if next_run_at is None else next_run_at,
        )
        row.schedule_enabled = normalized_schedule_enabled
        row.cron_expression = normalized_cron_expression
        row.next_run_at = normalized_next_run_at
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    if steps is not None:
        _replace_steps(session, workflow_id=int(row.id or 0), steps=steps)
    session.commit()
    session.refresh(row)
    return _workflow_read(session, row)


def list_workflows(
    session: Session,
    *,
    enabled: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowDefinitionListResponse:
    limit, offset = clamp_workflow_pagination(limit=limit, offset=offset)
    filters = []
    if enabled is not None:
        filters.append(WorkflowDefinition.enabled == enabled)
    total_items = int(session.exec(select(func.count()).select_from(WorkflowDefinition).where(*filters)).one())
    rows = session.exec(
        select(WorkflowDefinition)
        .where(*filters)
        .order_by(WorkflowDefinition.created_at.asc(), WorkflowDefinition.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return WorkflowDefinitionListResponse(
        items=[_workflow_read(session, row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_workflow(session: Session, *, workflow_id: int) -> WorkflowDefinitionRead:
    return _workflow_read(session, _get_workflow_row(session, workflow_id=workflow_id))


def enable_workflow(session: Session, *, workflow_id: int) -> WorkflowDefinitionRead:
    row = _get_workflow_row(session, workflow_id=workflow_id)
    row.enabled = True
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_read(session, row)


def disable_workflow(session: Session, *, workflow_id: int) -> WorkflowDefinitionRead:
    row = _get_workflow_row(session, workflow_id=workflow_id)
    row.enabled = False
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_read(session, row)
