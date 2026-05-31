from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import InventoryCopy, ScanImage
from app.models.condition_intelligence import (
    ConditionAgentExecution,
    ConditionDefect,
    ConditionProfile,
    ConditionSubgrade,
    ScanAnalysis,
    ScanQualityAssessment,
)
from app.schemas.condition_intelligence import ScanAnalysisRead

AGENT_SCAN_QUALITY = "scan_quality"
AGENT_DEFECT_DETECTION = "defect_detection"
AGENT_CONDITION_PROFILE = "condition_profile"
AGENT_SUBGRADE = "subgrade"


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_analysis_for_owner(session: Session, *, analysis_id: int, owner_user_id: int) -> ScanAnalysis:
    row = session.get(ScanAnalysis, analysis_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan analysis not found.")
    return row


def _validate_image_owner(session: Session, *, image_id: int | None, owner_user_id: int) -> None:
    if image_id is None:
        return
    image = session.get(ScanImage, image_id)
    if image is None or image.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan image not found.")


def _validate_inventory_owner(session: Session, *, inventory_copy_id: int | None, owner_user_id: int) -> None:
    if inventory_copy_id is None:
        return
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")


def create_scan_analysis(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int | None = None,
    front_image_id: int | None = None,
    back_image_id: int | None = None,
) -> ScanAnalysisRead:
    if front_image_id is None and back_image_id is None and inventory_copy_id is None:
        raise HTTPException(status_code=400, detail="At least one of front_image_id, back_image_id, or inventory_copy_id is required.")
    _validate_image_owner(session, image_id=front_image_id, owner_user_id=owner_user_id)
    _validate_image_owner(session, image_id=back_image_id, owner_user_id=owner_user_id)
    _validate_inventory_owner(session, inventory_copy_id=inventory_copy_id, owner_user_id=owner_user_id)

    row = ScanAnalysis(
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
        front_image_id=front_image_id,
        back_image_id=back_image_id,
        analysis_status="READY",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return ScanAnalysisRead.model_validate(row)


def resolve_or_create_analysis(
    session: Session,
    *,
    owner_user_id: int,
    analysis_id: int | None,
    inventory_copy_id: int | None,
    front_image_id: int | None,
    back_image_id: int | None,
) -> ScanAnalysis:
    if analysis_id is not None:
        return get_analysis_for_owner(session, analysis_id=analysis_id, owner_user_id=owner_user_id)
    read = create_scan_analysis(
        session,
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
        front_image_id=front_image_id,
        back_image_id=back_image_id,
    )
    row = session.get(ScanAnalysis, read.id)
    assert row is not None
    return row


def start_condition_agent_execution(
    session: Session,
    *,
    analysis_id: int,
    agent_code: str,
) -> ConditionAgentExecution:
    row = ConditionAgentExecution(
        analysis_id=analysis_id,
        agent_code=agent_code,
        status="RUNNING",
        started_at=_utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def complete_condition_agent_execution(
    session: Session,
    *,
    execution: ConditionAgentExecution,
    status: str = "COMPLETED",
) -> ConditionAgentExecution:
    completed_at = _utc_now()
    started_at = _ensure_aware(execution.started_at)
    duration_ms = int((completed_at - started_at).total_seconds() * 1000)
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = duration_ms
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def run_with_execution(
    session: Session,
    *,
    analysis_id: int,
    agent_code: str,
    runner,
):
    execution = start_condition_agent_execution(session, analysis_id=analysis_id, agent_code=agent_code)
    try:
        result = runner()
        complete_condition_agent_execution(session, execution=execution, status="COMPLETED")
        return result, execution
    except Exception:
        execution.status = "FAILED"
        execution.completed_at = _utc_now()
        started_at = _ensure_aware(execution.started_at)
        execution.duration_ms = int((execution.completed_at - started_at).total_seconds() * 1000)
        session.add(execution)
        session.commit()
        raise


def list_analyses_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ScanAnalysisRead], int]:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ScanAnalysis)
        .where(ScanAnalysis.owner_user_id == owner_user_id)
        .order_by(ScanAnalysis.created_at.desc(), ScanAnalysis.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [ScanAnalysisRead.model_validate(row) for row in page], len(rows)


def list_quality_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ScanQualityAssessment], int]:
    limit, offset = _paginate(limit, offset)
    analysis_ids = session.exec(select(ScanAnalysis.id).where(ScanAnalysis.owner_user_id == owner_user_id)).all()
    ids = [int(row) for row in analysis_ids if row is not None]
    if not ids:
        return [], 0
    rows = session.exec(
        select(ScanQualityAssessment)
        .where(ScanQualityAssessment.analysis_id.in_(ids))
        .order_by(ScanQualityAssessment.created_at.desc(), ScanQualityAssessment.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)


def list_profiles_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit, offset = _paginate(limit, offset)
    analysis_ids = [int(x) for x in session.exec(select(ScanAnalysis.id).where(ScanAnalysis.owner_user_id == owner_user_id)).all() if x]
    if not analysis_ids:
        return [], 0
    rows = session.exec(
        select(ConditionProfile)
        .where(ConditionProfile.analysis_id.in_(analysis_ids))
        .order_by(ConditionProfile.created_at.desc(), ConditionProfile.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)


def list_defects_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit, offset = _paginate(limit, offset)
    analysis_ids = [int(x) for x in session.exec(select(ScanAnalysis.id).where(ScanAnalysis.owner_user_id == owner_user_id)).all() if x]
    if not analysis_ids:
        return [], 0
    rows = session.exec(
        select(ConditionDefect)
        .where(ConditionDefect.analysis_id.in_(analysis_ids))
        .order_by(ConditionDefect.created_at.desc(), ConditionDefect.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)


def list_subgrades_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit, offset = _paginate(limit, offset)
    analysis_ids = [int(x) for x in session.exec(select(ScanAnalysis.id).where(ScanAnalysis.owner_user_id == owner_user_id)).all() if x]
    if not analysis_ids:
        return [], 0
    rows = session.exec(
        select(ConditionSubgrade)
        .where(ConditionSubgrade.analysis_id.in_(analysis_ids))
        .order_by(ConditionSubgrade.created_at.desc(), ConditionSubgrade.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)


def list_executions_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit, offset = _paginate(limit, offset)
    analysis_ids = [int(x) for x in session.exec(select(ScanAnalysis.id).where(ScanAnalysis.owner_user_id == owner_user_id)).all() if x]
    if not analysis_ids:
        return [], 0
    rows = session.exec(
        select(ConditionAgentExecution)
        .where(ConditionAgentExecution.analysis_id.in_(analysis_ids))
        .order_by(ConditionAgentExecution.started_at.desc(), ConditionAgentExecution.id.desc())
    ).all()
    return rows[offset : offset + limit], len(rows)
