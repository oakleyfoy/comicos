from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.grading_intelligence import GradingAgentExecution


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


AGENT_GRADE_PREDICTION = "grade_prediction"
AGENT_GRADING_RECOMMENDATION = "grading_recommendation"
AGENT_GRADING_ROI = "grading_roi"
AGENT_SUBMISSION_PRIORITY = "submission_priority"


def start_grading_agent_execution(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str,
    analysis_id: int | None = None,
) -> GradingAgentExecution:
    row = GradingAgentExecution(
        owner_user_id=owner_user_id,
        analysis_id=analysis_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=_utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def complete_grading_agent_execution(
    session: Session,
    *,
    execution: GradingAgentExecution,
    status: str = "COMPLETED",
) -> GradingAgentExecution:
    completed_at = _utc_now()
    started_at = _ensure_aware(execution.started_at)
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def run_with_grading_execution(session: Session, *, owner_user_id: int, agent_code: str, analysis_id: int | None, runner):
    execution = start_grading_agent_execution(
        session, owner_user_id=owner_user_id, agent_code=agent_code, analysis_id=analysis_id
    )
    try:
        result = runner()
        complete_grading_agent_execution(session, execution=execution, status="COMPLETED")
        return result, execution
    except Exception:
        execution.status = "FAILED"
        execution.completed_at = _utc_now()
        started_at = _ensure_aware(execution.started_at)
        execution.duration_ms = int((execution.completed_at - started_at).total_seconds() * 1000)
        session.add(execution)
        session.commit()
        raise


def get_recommendation_for_owner(session: Session, *, recommendation_id: int, owner_user_id: int):
    from app.models.grading_intelligence import GradingRecommendation

    row = session.get(GradingRecommendation, recommendation_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Grading recommendation not found.")
    return row


def list_executions_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
):
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(GradingAgentExecution)
        .where(GradingAgentExecution.owner_user_id == owner_user_id)
        .order_by(GradingAgentExecution.started_at.desc(), GradingAgentExecution.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)
