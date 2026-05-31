from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.spec_intelligence import SpecAgentExecution, SpecRecommendation


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


AGENT_SPEC_SCORING = "spec_scoring"
AGENT_SPEC_RECOMMENDATION = "spec_recommendation"
AGENT_WEEKLY_BUY_LIST = "weekly_buy_list"


def start_spec_execution(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str,
) -> SpecAgentExecution:
    row = SpecAgentExecution(
        owner_user_id=owner_user_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=_utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def complete_spec_execution(
    session: Session,
    *,
    execution: SpecAgentExecution,
    status: str = "COMPLETED",
) -> SpecAgentExecution:
    completed_at = _utc_now()
    started_at = _ensure_aware(execution.started_at)
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def run_with_spec_execution(session: Session, *, owner_user_id: int, agent_code: str, runner):
    execution = start_spec_execution(session, owner_user_id=owner_user_id, agent_code=agent_code)
    try:
        result = runner()
        complete_spec_execution(session, execution=execution, status="COMPLETED")
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
        select(SpecAgentExecution)
        .where(SpecAgentExecution.owner_user_id == owner_user_id)
        .order_by(SpecAgentExecution.started_at.desc(), SpecAgentExecution.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)


def get_recommendation_for_owner(session: Session, *, recommendation_id: int, owner_user_id: int) -> SpecRecommendation:
    row = session.get(SpecRecommendation, recommendation_id)
    if row is None:
        raise ValueError("Spec recommendation not found.")
    from app.models.release_intelligence import ReleaseIssue

    issue = session.get(ReleaseIssue, row.release_issue_id)
    if issue is None or issue.owner_user_id != owner_user_id:
        raise ValueError("Spec recommendation not found.")
    return row
