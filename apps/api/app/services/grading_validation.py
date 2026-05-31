from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.grading_validation import GradingValidationExecution


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


AGENT_GRADE_VALIDATION = "grade_validation"
AGENT_GRADING_CALIBRATION = "grading_calibration"
AGENT_GRADING_RELIABILITY = "grading_reliability"
AGENT_GRADING_OUTCOMES = "grading_outcomes"


def start_validation_execution(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str,
) -> GradingValidationExecution:
    row = GradingValidationExecution(
        owner_user_id=owner_user_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=_utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def complete_validation_execution(
    session: Session,
    *,
    execution: GradingValidationExecution,
    status: str = "COMPLETED",
) -> GradingValidationExecution:
    completed_at = _utc_now()
    started_at = _ensure_aware(execution.started_at)
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def run_with_validation_execution(session: Session, *, owner_user_id: int, agent_code: str, runner):
    execution = start_validation_execution(session, owner_user_id=owner_user_id, agent_code=agent_code)
    try:
        result = runner()
        complete_validation_execution(session, execution=execution, status="COMPLETED")
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
        select(GradingValidationExecution)
        .where(GradingValidationExecution.owner_user_id == owner_user_id)
        .order_by(GradingValidationExecution.started_at.desc(), GradingValidationExecution.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)
