from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseAgentExecution


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


AGENT_NEW_NUMBER_ONE = "new_number_one"
AGENT_KEY_ISSUE = "key_issue"
AGENT_VARIANT_INTELLIGENCE = "variant_intelligence"


def start_release_execution(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str,
) -> ReleaseAgentExecution:
    row = ReleaseAgentExecution(
        owner_user_id=owner_user_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=_utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def complete_release_execution(
    session: Session,
    *,
    execution: ReleaseAgentExecution,
    status: str = "COMPLETED",
) -> ReleaseAgentExecution:
    completed_at = _utc_now()
    started_at = _ensure_aware(execution.started_at)
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def run_with_release_execution(session: Session, *, owner_user_id: int, agent_code: str, runner):
    execution = start_release_execution(session, owner_user_id=owner_user_id, agent_code=agent_code)
    try:
        result = runner()
        complete_release_execution(session, execution=execution, status="COMPLETED")
        return result, execution
    except Exception:
        execution.status = "FAILED"
        execution.completed_at = _utc_now()
        started_at = _ensure_aware(execution.started_at)
        execution.duration_ms = int((execution.completed_at - started_at).total_seconds() * 1000)
        session.add(execution)
        session.commit()
        raise


def list_executions_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
):
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ReleaseAgentExecution)
        .where(ReleaseAgentExecution.owner_user_id == owner_user_id)
        .order_by(ReleaseAgentExecution.started_at.desc(), ReleaseAgentExecution.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)
