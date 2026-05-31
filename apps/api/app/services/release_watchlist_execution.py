from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.release_watchlist import WatchlistAgentExecution


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


AGENT_RUN_CONTINUITY = "run_continuity"
AGENT_FOC_REMINDERS = "foc_reminders"
AGENT_RELEASE_REMINDERS = "release_reminders"
AGENT_AUTO_WATCHLISTS = "auto_watchlists"


def start_watchlist_execution(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str,
) -> WatchlistAgentExecution:
    row = WatchlistAgentExecution(
        owner_user_id=owner_user_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=_utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def complete_watchlist_execution(
    session: Session,
    *,
    execution: WatchlistAgentExecution,
    status: str = "COMPLETED",
) -> WatchlistAgentExecution:
    completed_at = _utc_now()
    started_at = _ensure_aware(execution.started_at)
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def run_with_watchlist_execution(session: Session, *, owner_user_id: int, agent_code: str, runner):
    execution = start_watchlist_execution(session, owner_user_id=owner_user_id, agent_code=agent_code)
    try:
        result = runner()
        complete_watchlist_execution(session, execution=execution, status="COMPLETED")
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
        select(WatchlistAgentExecution)
        .where(WatchlistAgentExecution.owner_user_id == owner_user_id)
        .order_by(WatchlistAgentExecution.started_at.desc(), WatchlistAgentExecution.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)
