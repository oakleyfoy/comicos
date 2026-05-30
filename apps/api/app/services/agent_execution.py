from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import AgentExecution, AgentExecutionEvent
from app.schemas.agent import (
    AgentExecutionDetail,
    AgentExecutionEventRead,
    AgentExecutionListResponse,
    AgentExecutionRead,
)
from app.services.agent_permissions import EXECUTE_PERMISSION_CAPABILITY, check_permission
from app.services.agent_registry import clamp_agent_pagination, get_agent

AGENT_EXECUTION_STATUS_PENDING = "PENDING"
AGENT_EXECUTION_STATUS_RUNNING = "RUNNING"
AGENT_EXECUTION_STATUS_COMPLETED = "COMPLETED"
AGENT_EXECUTION_STATUS_FAILED = "FAILED"

_ACTIVE_EXECUTION_STATUSES = {AGENT_EXECUTION_STATUS_PENDING, AGENT_EXECUTION_STATUS_RUNNING}
_TERMINAL_EXECUTION_STATUSES = {AGENT_EXECUTION_STATUS_COMPLETED, AGENT_EXECUTION_STATUS_FAILED}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _execution_row(session: Session, *, execution_id: int) -> AgentExecution:
    row = session.get(AgentExecution, execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent execution not found.")
    return row


def _event_rows(session: Session, *, execution_id: int) -> list[AgentExecutionEvent]:
    return session.exec(
        select(AgentExecutionEvent)
        .where(AgentExecutionEvent.execution_id == execution_id)
        .order_by(AgentExecutionEvent.event_timestamp.asc(), AgentExecutionEvent.id.asc())
    ).all()


def _execution_read(row: AgentExecution) -> AgentExecutionRead:
    return AgentExecutionRead(
        id=int(row.id or 0),
        agent_id=row.agent_id,
        execution_uuid=row.execution_uuid,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        execution_duration_ms=row.execution_duration_ms,
        triggered_by=row.triggered_by,
        trigger_source=row.trigger_source,
    )


def _event_read(row: AgentExecutionEvent) -> AgentExecutionEventRead:
    return AgentExecutionEventRead(
        id=int(row.id or 0),
        execution_id=row.execution_id,
        event_type=row.event_type,
        event_timestamp=row.event_timestamp,
        event_payload_json=row.event_payload_json,
    )


def _detail(session: Session, row: AgentExecution) -> AgentExecutionDetail:
    return AgentExecutionDetail(
        agent=get_agent(session, agent_id=row.agent_id),
        execution=_execution_read(row),
        events=[_event_read(event) for event in _event_rows(session, execution_id=int(row.id or 0))],
    )


def _require_nonterminal(row: AgentExecution) -> None:
    if row.status in _TERMINAL_EXECUTION_STATUSES:
        raise HTTPException(status_code=409, detail="Agent execution is already terminal.")


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return max(0, int((_as_utc(completed_at) - _as_utc(started_at)).total_seconds() * 1000))


def _enforce_execution_permissions(
    session: Session,
    *,
    agent_id: int,
    agent_code: str,
    triggered_by: str,
    trigger_source: str,
    capability_codes: list[str],
) -> None:
    execute_check = check_permission(
        session,
        agent_id=agent_id,
        capability_code=EXECUTE_PERMISSION_CAPABILITY,
        permission_scope="execute",
        action_code="start_execution",
        event_payload_json={
            "agent_code": agent_code,
            "triggered_by": triggered_by,
            "trigger_source": trigger_source,
        },
    )
    if not execute_check.allowed:
        raise HTTPException(status_code=403, detail=f"Agent {agent_code} is missing execute permission.")
    for capability_code in sorted(code for code in capability_codes if code.endswith(".read")):
        read_check = check_permission(
            session,
            agent_id=agent_id,
            capability_code=capability_code,
            permission_scope="read",
            action_code="start_execution",
            event_payload_json={
                "agent_code": agent_code,
                "triggered_by": triggered_by,
                "trigger_source": trigger_source,
            },
        )
        if not read_check.allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Agent {agent_code} is missing required read permission for {capability_code}.",
            )


def log_event(
    session: Session,
    *,
    execution_id: int,
    event_type: str,
    event_payload_json: dict | None = None,
    event_timestamp: datetime | None = None,
) -> AgentExecutionEventRead:
    execution_row = _execution_row(session, execution_id=execution_id)
    _require_nonterminal(execution_row)
    timestamp = event_timestamp or utc_now()
    row = AgentExecutionEvent(
        execution_id=execution_id,
        event_type=event_type.strip(),
        event_timestamp=timestamp,
        event_payload_json=_json_safe(event_payload_json or {}),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _event_read(row)


def start_execution(
    session: Session,
    *,
    agent_id: int,
    triggered_by: str,
    trigger_source: str,
    enforce_permissions: bool = True,
) -> AgentExecutionDetail:
    agent = get_agent(session, agent_id=agent_id)
    if not agent.enabled:
        raise HTTPException(status_code=409, detail=f"Agent {agent.code} is disabled.")
    if enforce_permissions:
        _enforce_execution_permissions(
            session,
            agent_id=agent_id,
            agent_code=agent.code,
            triggered_by=triggered_by.strip(),
            trigger_source=trigger_source.strip(),
            capability_codes=[capability.capability_code for capability in agent.capabilities],
        )
    now = utc_now()
    row = AgentExecution(
        agent_id=agent_id,
        execution_uuid=str(uuid.uuid4()),
        status=AGENT_EXECUTION_STATUS_RUNNING,
        started_at=now,
        triggered_by=triggered_by.strip(),
        trigger_source=trigger_source.strip(),
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    session.add(
        AgentExecutionEvent(
            execution_id=int(row.id),
            event_type="execution_started",
            event_timestamp=now,
            event_payload_json=_json_safe(
                {
                    "agent_id": agent_id,
                    "status": AGENT_EXECUTION_STATUS_RUNNING,
                    "triggered_by": triggered_by.strip(),
                    "trigger_source": trigger_source.strip(),
                }
            ),
        )
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def complete_execution(
    session: Session,
    *,
    execution_id: int,
    event_payload_json: dict | None = None,
) -> AgentExecutionDetail:
    row = _execution_row(session, execution_id=execution_id)
    _require_nonterminal(row)
    completed_at = utc_now()
    row.status = AGENT_EXECUTION_STATUS_COMPLETED
    row.completed_at = completed_at
    row.execution_duration_ms = _duration_ms(row.started_at, completed_at)
    session.add(row)
    session.flush()
    session.add(
        AgentExecutionEvent(
            execution_id=execution_id,
            event_type="execution_completed",
            event_timestamp=completed_at,
            event_payload_json=_json_safe(
                {
                    **(event_payload_json or {}),
                    "status": AGENT_EXECUTION_STATUS_COMPLETED,
                    "execution_duration_ms": row.execution_duration_ms,
                }
            ),
        )
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def fail_execution(
    session: Session,
    *,
    execution_id: int,
    event_payload_json: dict | None = None,
) -> AgentExecutionDetail:
    row = _execution_row(session, execution_id=execution_id)
    _require_nonterminal(row)
    failed_at = utc_now()
    row.status = AGENT_EXECUTION_STATUS_FAILED
    row.completed_at = failed_at
    row.execution_duration_ms = _duration_ms(row.started_at, failed_at)
    session.add(row)
    session.flush()
    session.add(
        AgentExecutionEvent(
            execution_id=execution_id,
            event_type="execution_failed",
            event_timestamp=failed_at,
            event_payload_json=_json_safe(
                {
                    **(event_payload_json or {}),
                    "status": AGENT_EXECUTION_STATUS_FAILED,
                    "execution_duration_ms": row.execution_duration_ms,
                }
            ),
        )
    )
    session.commit()
    session.refresh(row)
    return _detail(session, row)


def list_executions(
    session: Session,
    *,
    agent_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AgentExecutionListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    filters = []
    if agent_id is not None:
        filters.append(AgentExecution.agent_id == agent_id)
    if status is not None:
        filters.append(AgentExecution.status == status.strip().upper())
    total_items = int(session.exec(select(func.count()).select_from(AgentExecution).where(*filters)).one())
    rows = session.exec(
        select(AgentExecution)
        .where(*filters)
        .order_by(AgentExecution.started_at.asc(), AgentExecution.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AgentExecutionListResponse(
        items=[_execution_read(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_execution(session: Session, *, execution_id: int) -> AgentExecutionDetail:
    return _detail(session, _execution_row(session, execution_id=execution_id))
