from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import AgentExecution, ResearchFinding, ResearchSnapshot
from app.schemas.research_agent import (
    ResearchFindingListResponse,
    ResearchFindingRead,
    ResearchSnapshotDetail,
    ResearchSnapshotListResponse,
    ResearchSnapshotRead,
)
from app.services.agent_registry import clamp_agent_pagination
from app.services.research_agent_base import (
    RESEARCH_FINDING_STATUS_DISMISSED,
    RESEARCH_FINDING_STATUS_REVIEWED,
    _finding_read,
    _snapshot_read,
    get_finding_read,
    get_snapshot_detail,
)


def _owner_scope_value(owner_user_id: int) -> str:
    return str(owner_user_id)


def _snapshot_visibility_statement(*, owner_user_id: int):
    return (
        select(ResearchSnapshot)
        .join(AgentExecution, AgentExecution.id == ResearchSnapshot.agent_execution_id)
        .where(AgentExecution.triggered_by == _owner_scope_value(owner_user_id))
    )


def _finding_visibility_statement(*, owner_user_id: int):
    return (
        select(ResearchFinding)
        .join(ResearchSnapshot, ResearchSnapshot.id == ResearchFinding.snapshot_id)
        .join(AgentExecution, AgentExecution.id == ResearchSnapshot.agent_execution_id)
        .where(AgentExecution.triggered_by == _owner_scope_value(owner_user_id))
    )


def _visible_snapshot_row(session: Session, *, owner_user_id: int, snapshot_id: int) -> ResearchSnapshot:
    row = session.exec(_snapshot_visibility_statement(owner_user_id=owner_user_id).where(ResearchSnapshot.id == snapshot_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Research snapshot not found.")
    return row


def _visible_finding_row(session: Session, *, owner_user_id: int, finding_id: int) -> ResearchFinding:
    row = session.exec(_finding_visibility_statement(owner_user_id=owner_user_id).where(ResearchFinding.id == finding_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Research finding not found.")
    return row


def list_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str | None = None,
    research_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ResearchSnapshotListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    stmt = _snapshot_visibility_statement(owner_user_id=owner_user_id)
    count_stmt = (
        select(func.count())
        .select_from(ResearchSnapshot)
        .join(AgentExecution, AgentExecution.id == ResearchSnapshot.agent_execution_id)
        .where(AgentExecution.triggered_by == _owner_scope_value(owner_user_id))
    )
    if agent_code is not None:
        normalized = agent_code.strip().lower()
        stmt = stmt.where(ResearchSnapshot.agent_code == normalized)
        count_stmt = count_stmt.where(ResearchSnapshot.agent_code == normalized)
    if research_type is not None:
        normalized = research_type.strip().lower()
        stmt = stmt.where(ResearchSnapshot.research_type == normalized)
        count_stmt = count_stmt.where(ResearchSnapshot.research_type == normalized)
    if status is not None:
        normalized = status.strip().upper()
        stmt = stmt.where(ResearchSnapshot.status == normalized)
        count_stmt = count_stmt.where(ResearchSnapshot.status == normalized)
    total_items = int(session.exec(count_stmt).one())
    rows = session.exec(
        stmt.order_by(ResearchSnapshot.generated_at.asc(), ResearchSnapshot.id.asc()).offset(offset).limit(limit)
    ).all()
    return ResearchSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_snapshot_detail_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int,
) -> ResearchSnapshotDetail:
    row = _visible_snapshot_row(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    return get_snapshot_detail(session, snapshot_id=int(row.id or 0))


def list_findings(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int | None = None,
    finding_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ResearchFindingListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    stmt = _finding_visibility_statement(owner_user_id=owner_user_id)
    count_stmt = (
        select(func.count())
        .select_from(ResearchFinding)
        .join(ResearchSnapshot, ResearchSnapshot.id == ResearchFinding.snapshot_id)
        .join(AgentExecution, AgentExecution.id == ResearchSnapshot.agent_execution_id)
        .where(AgentExecution.triggered_by == _owner_scope_value(owner_user_id))
    )
    if snapshot_id is not None:
        _visible_snapshot_row(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
        stmt = stmt.where(ResearchFinding.snapshot_id == snapshot_id)
        count_stmt = count_stmt.where(ResearchFinding.snapshot_id == snapshot_id)
    if finding_type is not None:
        normalized = finding_type.strip().lower()
        stmt = stmt.where(ResearchFinding.finding_type == normalized)
        count_stmt = count_stmt.where(ResearchFinding.finding_type == normalized)
    if status is not None:
        normalized = status.strip().upper()
        stmt = stmt.where(ResearchFinding.status == normalized)
        count_stmt = count_stmt.where(ResearchFinding.status == normalized)
    total_items = int(session.exec(count_stmt).one())
    rows = session.exec(
        stmt.order_by(ResearchFinding.created_at.asc(), ResearchFinding.id.asc()).offset(offset).limit(limit)
    ).all()
    return ResearchFindingListResponse(
        items=[_finding_read(session, row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_finding(session: Session, *, owner_user_id: int, finding_id: int) -> ResearchFindingRead:
    row = _visible_finding_row(session, owner_user_id=owner_user_id, finding_id=finding_id)
    return get_finding_read(session, finding_id=int(row.id or 0))


def _set_finding_status(
    session: Session,
    *,
    owner_user_id: int,
    finding_id: int,
    status: str,
) -> ResearchFindingRead:
    row = _visible_finding_row(session, owner_user_id=owner_user_id, finding_id=finding_id)
    row.status = status
    session.add(row)
    session.commit()
    session.refresh(row)
    return get_finding_read(session, finding_id=int(row.id or 0))


def mark_finding_reviewed(session: Session, *, owner_user_id: int, finding_id: int) -> ResearchFindingRead:
    return _set_finding_status(
        session,
        owner_user_id=owner_user_id,
        finding_id=finding_id,
        status=RESEARCH_FINDING_STATUS_REVIEWED,
    )


def mark_finding_dismissed(session: Session, *, owner_user_id: int, finding_id: int) -> ResearchFindingRead:
    return _set_finding_status(
        session,
        owner_user_id=owner_user_id,
        finding_id=finding_id,
        status=RESEARCH_FINDING_STATUS_DISMISSED,
    )
