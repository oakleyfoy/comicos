from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from app.models import AgentDefinition, AgentExecution, WorkflowDefinition, WorkflowExecution
from app.schemas.agent_dashboard import (
    AgentHealthListResponse,
    AgentHealthRead,
    WorkflowHealthListResponse,
    WorkflowHealthRead,
)
from app.services.agent_registry import clamp_agent_pagination
from app.services.workflow_registry import clamp_workflow_pagination


HEALTH_STATUS_HEALTHY = "HEALTHY"
HEALTH_STATUS_WARNING = "WARNING"
HEALTH_STATUS_FAILED = "FAILED"
HEALTH_STATUS_DISABLED = "DISABLED"

_TERMINAL_SUCCESS = {"COMPLETED"}
_TERMINAL_FAILURE = {"FAILED"}


def _average_duration_ms(rows: list[int | None]) -> int | None:
    durations = [int(value) for value in rows if value is not None]
    if not durations:
        return None
    return int(sum(durations) / len(durations))


def _success_rate(*, success_count: int, execution_count: int) -> float:
    if execution_count <= 0:
        return 0.0
    return round(success_count / execution_count, 4)


def _latest_timestamp(rows: list[datetime | None]) -> datetime | None:
    timestamps = [value for value in rows if value is not None]
    if not timestamps:
        return None
    return max(timestamps)


def _health_status(
    *,
    enabled: bool,
    success_count: int,
    failure_count: int,
    last_success_at: datetime | None,
    last_failure_at: datetime | None,
) -> str:
    if not enabled:
        return HEALTH_STATUS_DISABLED
    if failure_count > 0 and (last_success_at is None or (last_failure_at is not None and last_failure_at >= last_success_at)):
        return HEALTH_STATUS_FAILED
    if failure_count > 0:
        return HEALTH_STATUS_WARNING
    return HEALTH_STATUS_HEALTHY


def list_agent_health(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> AgentHealthListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    agent_rows = session.exec(
        select(AgentDefinition).order_by(AgentDefinition.created_at.asc(), AgentDefinition.id.asc())
    ).all()
    execution_rows = session.exec(
        select(AgentExecution)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(AgentExecution.started_at.asc(), AgentExecution.id.asc())
    ).all()
    executions_by_agent: dict[int, list[AgentExecution]] = {}
    for row in execution_rows:
        executions_by_agent.setdefault(row.agent_id, []).append(row)

    items = []
    for agent in agent_rows:
        agent_id = int(agent.id or 0)
        rows = executions_by_agent.get(agent_id, [])
        success_rows = [row for row in rows if row.status in _TERMINAL_SUCCESS]
        failure_rows = [row for row in rows if row.status in _TERMINAL_FAILURE]
        last_success_at = _latest_timestamp([row.completed_at for row in success_rows])
        last_failure_at = _latest_timestamp([row.completed_at for row in failure_rows])
        items.append(
            AgentHealthRead(
                agent_id=agent_id,
                agent_code=agent.code,
                agent_name=agent.name,
                enabled=agent.enabled,
                health_status=_health_status(
                    enabled=agent.enabled,
                    success_count=len(success_rows),
                    failure_count=len(failure_rows),
                    last_success_at=last_success_at,
                    last_failure_at=last_failure_at,
                ),
                execution_count=len(rows),
                success_count=len(success_rows),
                failure_count=len(failure_rows),
                success_rate=_success_rate(success_count=len(success_rows), execution_count=len(rows)),
                average_duration_ms=_average_duration_ms([row.execution_duration_ms for row in rows]),
                last_run_at=_latest_timestamp([row.started_at for row in rows]),
                last_success_at=last_success_at,
                last_failure_at=last_failure_at,
            )
        )

    return AgentHealthListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def list_workflow_health(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> WorkflowHealthListResponse:
    limit, offset = clamp_workflow_pagination(limit=limit, offset=offset)
    workflow_rows = session.exec(
        select(WorkflowDefinition).order_by(WorkflowDefinition.created_at.asc(), WorkflowDefinition.id.asc())
    ).all()
    execution_rows = session.exec(
        select(WorkflowExecution)
        .where(WorkflowExecution.triggered_by == str(owner_user_id))
        .order_by(WorkflowExecution.started_at.asc(), WorkflowExecution.id.asc())
    ).all()
    executions_by_workflow: dict[int, list[WorkflowExecution]] = {}
    for row in execution_rows:
        executions_by_workflow.setdefault(row.workflow_id, []).append(row)

    items = []
    for workflow in workflow_rows:
        workflow_id = int(workflow.id or 0)
        rows = executions_by_workflow.get(workflow_id, [])
        success_rows = [row for row in rows if row.status in _TERMINAL_SUCCESS]
        failure_rows = [row for row in rows if row.status in _TERMINAL_FAILURE]
        last_success_at = _latest_timestamp([row.completed_at for row in success_rows])
        last_failure_at = _latest_timestamp([row.completed_at for row in failure_rows])
        items.append(
            WorkflowHealthRead(
                workflow_id=workflow_id,
                workflow_code=workflow.workflow_code,
                workflow_name=workflow.workflow_name,
                enabled=workflow.enabled,
                health_status=_health_status(
                    enabled=workflow.enabled,
                    success_count=len(success_rows),
                    failure_count=len(failure_rows),
                    last_success_at=last_success_at,
                    last_failure_at=last_failure_at,
                ),
                execution_count=len(rows),
                success_count=len(success_rows),
                failure_count=len(failure_rows),
                success_rate=_success_rate(success_count=len(success_rows), execution_count=len(rows)),
                average_duration_ms=_average_duration_ms([row.duration_ms for row in rows]),
                last_run_at=_latest_timestamp([row.started_at for row in rows]),
                last_success_at=last_success_at,
                last_failure_at=last_failure_at,
            )
        )

    return WorkflowHealthListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )
