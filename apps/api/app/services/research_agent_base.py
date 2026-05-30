from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import AgentExecution, ResearchEvidence, ResearchFinding, ResearchSnapshot
from app.schemas.research_agent import (
    ResearchEvidenceRead,
    ResearchFindingRead,
    ResearchSnapshotDetail,
    ResearchSnapshotRead,
)

RESEARCH_SNAPSHOT_STATUS_RUNNING = "RUNNING"
RESEARCH_SNAPSHOT_STATUS_COMPLETED = "COMPLETED"
RESEARCH_SNAPSHOT_STATUS_FAILED = "FAILED"

RESEARCH_FINDING_STATUS_OPEN = "OPEN"
RESEARCH_FINDING_STATUS_REVIEWED = "REVIEWED"
RESEARCH_FINDING_STATUS_DISMISSED = "DISMISSED"

_TERMINAL_SNAPSHOT_STATUSES = {RESEARCH_SNAPSHOT_STATUS_COMPLETED, RESEARCH_SNAPSHOT_STATUS_FAILED}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _execution_row(session: Session, *, agent_execution_id: int) -> AgentExecution:
    row = session.get(AgentExecution, agent_execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent execution not found.")
    return row


def _snapshot_row(session: Session, *, snapshot_id: int) -> ResearchSnapshot:
    row = session.get(ResearchSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research snapshot not found.")
    return row


def _finding_row(session: Session, *, finding_id: int) -> ResearchFinding:
    row = session.get(ResearchFinding, finding_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research finding not found.")
    return row


def _evidence_rows(session: Session, *, finding_id: int) -> list[ResearchEvidence]:
    return session.exec(
        select(ResearchEvidence)
        .where(ResearchEvidence.finding_id == finding_id)
        .order_by(ResearchEvidence.created_at.asc(), ResearchEvidence.id.asc())
    ).all()


def _finding_rows(session: Session, *, snapshot_id: int) -> list[ResearchFinding]:
    return session.exec(
        select(ResearchFinding)
        .where(ResearchFinding.snapshot_id == snapshot_id)
        .order_by(ResearchFinding.created_at.asc(), ResearchFinding.id.asc())
    ).all()


def _snapshot_read(row: ResearchSnapshot) -> ResearchSnapshotRead:
    return ResearchSnapshotRead(
        id=int(row.id or 0),
        agent_execution_id=row.agent_execution_id,
        snapshot_uuid=row.snapshot_uuid,
        agent_code=row.agent_code,
        research_type=row.research_type,
        status=row.status,
        generated_at=row.generated_at,
        input_scope_json=row.input_scope_json,
        summary_json=row.summary_json,
        created_at=row.created_at,
    )


def _evidence_read(row: ResearchEvidence) -> ResearchEvidenceRead:
    return ResearchEvidenceRead(
        id=int(row.id or 0),
        finding_id=row.finding_id,
        evidence_type=row.evidence_type,
        source_name=row.source_name,
        source_url=row.source_url,
        source_payload_json=row.source_payload_json,
        evidence_score=row.evidence_score,
        created_at=row.created_at,
    )


def _finding_read(session: Session, row: ResearchFinding) -> ResearchFindingRead:
    return ResearchFindingRead(
        id=int(row.id or 0),
        snapshot_id=row.snapshot_id,
        finding_code=row.finding_code,
        finding_type=row.finding_type,
        title=row.title,
        description=row.description,
        confidence_score=row.confidence_score,
        priority_score=row.priority_score,
        status=row.status,
        recommendation_json=row.recommendation_json,
        created_at=row.created_at,
        evidence=[_evidence_read(evidence) for evidence in _evidence_rows(session, finding_id=int(row.id or 0))],
    )


def get_snapshot_detail(session: Session, *, snapshot_id: int) -> ResearchSnapshotDetail:
    row = _snapshot_row(session, snapshot_id=snapshot_id)
    return ResearchSnapshotDetail(
        snapshot=_snapshot_read(row),
        findings=[_finding_read(session, finding) for finding in _finding_rows(session, snapshot_id=snapshot_id)],
    )


def get_finding_read(session: Session, *, finding_id: int) -> ResearchFindingRead:
    return _finding_read(session, _finding_row(session, finding_id=finding_id))


def create_snapshot(
    session: Session,
    *,
    agent_execution_id: int,
    agent_code: str,
    research_type: str,
    input_scope_json: dict[str, Any] | None = None,
) -> ResearchSnapshotRead:
    _execution_row(session, agent_execution_id=agent_execution_id)
    now = utc_now()
    row = ResearchSnapshot(
        agent_execution_id=agent_execution_id,
        snapshot_uuid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"research-snapshot:{agent_execution_id}:{agent_code.strip().lower()}:{research_type.strip().lower()}",
            )
        ),
        agent_code=agent_code.strip().lower(),
        research_type=research_type.strip().lower(),
        status=RESEARCH_SNAPSHOT_STATUS_RUNNING,
        generated_at=now,
        input_scope_json=_json_safe(input_scope_json or {}),
        summary_json={},
        created_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _snapshot_read(row)


def add_finding(
    session: Session,
    *,
    snapshot_id: int,
    finding_code: str,
    finding_type: str,
    title: str,
    description: str,
    confidence_score: float,
    priority_score: float,
    recommendation_json: dict[str, Any] | None = None,
    status: str = RESEARCH_FINDING_STATUS_OPEN,
) -> ResearchFindingRead:
    snapshot = _snapshot_row(session, snapshot_id=snapshot_id)
    if snapshot.status in _TERMINAL_SNAPSHOT_STATUSES:
        raise HTTPException(status_code=409, detail="Research snapshot is already terminal.")
    row = ResearchFinding(
        snapshot_id=snapshot_id,
        finding_code=finding_code.strip().lower(),
        finding_type=finding_type.strip().lower(),
        title=title.strip(),
        description=description.strip(),
        confidence_score=max(0.0, float(confidence_score)),
        priority_score=max(0.0, float(priority_score)),
        status=status.strip().upper(),
        recommendation_json=_json_safe(recommendation_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _finding_read(session, row)


def add_evidence(
    session: Session,
    *,
    finding_id: int,
    evidence_type: str,
    source_name: str,
    source_url: str | None = None,
    source_payload_json: dict[str, Any] | None = None,
    evidence_score: float = 0.0,
) -> ResearchEvidenceRead:
    finding = _finding_row(session, finding_id=finding_id)
    snapshot = _snapshot_row(session, snapshot_id=finding.snapshot_id)
    if snapshot.status in _TERMINAL_SNAPSHOT_STATUSES:
        raise HTTPException(status_code=409, detail="Research snapshot is already terminal.")
    row = ResearchEvidence(
        finding_id=finding_id,
        evidence_type=evidence_type.strip().lower(),
        source_name=source_name.strip(),
        source_url=source_url.strip() if source_url else None,
        source_payload_json=_json_safe(source_payload_json or {}),
        evidence_score=max(0.0, float(evidence_score)),
        created_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _evidence_read(row)


def complete_snapshot(
    session: Session,
    *,
    snapshot_id: int,
    summary_json: dict[str, Any] | None = None,
) -> ResearchSnapshotRead:
    row = _snapshot_row(session, snapshot_id=snapshot_id)
    if row.status in _TERMINAL_SNAPSHOT_STATUSES:
        raise HTTPException(status_code=409, detail="Research snapshot is already terminal.")
    row.status = RESEARCH_SNAPSHOT_STATUS_COMPLETED
    row.summary_json = _json_safe(summary_json or {})
    session.add(row)
    session.commit()
    session.refresh(row)
    return _snapshot_read(row)


def fail_snapshot(
    session: Session,
    *,
    snapshot_id: int,
    summary_json: dict[str, Any] | None = None,
) -> ResearchSnapshotRead:
    row = _snapshot_row(session, snapshot_id=snapshot_id)
    if row.status in _TERMINAL_SNAPSHOT_STATUSES:
        raise HTTPException(status_code=409, detail="Research snapshot is already terminal.")
    row.status = RESEARCH_SNAPSHOT_STATUS_FAILED
    row.summary_json = _json_safe(summary_json or {})
    session.add(row)
    session.commit()
    session.refresh(row)
    return _snapshot_read(row)
