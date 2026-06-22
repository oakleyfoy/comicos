"""P37-01 operational grading candidate orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    GradingCandidate,
    GradingCandidateEvidence,
    GradingCandidateLifecycleEvent,
    GradingCandidateSnapshot,
    InventoryCopy,
)
from app.services.catalog_unification_issue_id import effective_catalog_issue_id
from app.schemas.grading_candidate import (
    GradingCandidateCreatePayload,
    GradingCandidateDashboardSummary,
    GradingCandidateDetailRead,
    GradingCandidateEvidenceCreatePayload,
    GradingCandidateEvidenceListResponse,
    GradingCandidateEvidenceRead,
    GradingCandidateGradePayload,
    GradingCandidateLifecycleEventListResponse,
    GradingCandidateLifecycleEventRead,
    GradingCandidateListResponse,
    GradingCandidatePatchPayload,
    GradingCandidateRead,
    GradingCandidateRejectPayload,
    GradingCandidateSnapshotRead,
    InventoryGradingCandidateBadge,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PIPELINE_STATUSES = frozenset({"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED"})

_PATCHABLE_STATUSES = frozenset({"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION"})

_GRADER_VALUES = frozenset({"PSA", "CGC", "CBCS", "RAW_ONLY"})
_PRIORITY_VALUES = frozenset({"LOW", "MEDIUM", "HIGH", "ELITE"})


def clamp_grading_list_pagination(limit: int, offset: int) -> tuple[int, int]:
    lim = min(max(limit, 1), 500)
    off = max(offset, 0)
    return lim, off


def _money_quantize(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.01"))


def _roi_quantize(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.00000001"))


def _money_key(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.01")), "f")


def _roi_key(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.00000001")), "f")


def evidence_count(session: Session, grading_candidate_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(GradingCandidateEvidence)
        .where(col(GradingCandidateEvidence.grading_candidate_id) == grading_candidate_id)
    )
    return int(session.exec(stmt).one())


def assumptions_payload(row: GradingCandidate, *, evidence_count_val: int) -> dict[str, object]:
    return {
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "canonical_comic_issue_id": row.canonical_comic_issue_id,
        "candidate_priority": row.candidate_priority,
        "estimated_graded_value": _money_key(row.estimated_graded_value),
        "estimated_grading_cost": _money_key(row.estimated_grading_cost),
        "estimated_raw_value": _money_key(row.estimated_raw_value),
        "estimated_roi": _roi_key(row.estimated_roi),
        "estimated_spread": _money_key(row.estimated_spread),
        "evidence_count": evidence_count_val,
        "graded_at": row.graded_at.isoformat() if row.graded_at else None,
        "inventory_item_id": row.inventory_item_id,
        "rationale": row.rationale,
        "status": row.status,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "target_grade": row.target_grade,
        "target_grader": row.target_grader,
        "updated_at": row.updated_at.isoformat(),
    }


def deterministic_checksum(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def append_snapshot(session: Session, row: GradingCandidate) -> GradingCandidateSnapshot:
    ec = evidence_count(session, int(row.id or 0))
    assumptions = assumptions_payload(row, evidence_count_val=ec)
    checksum = deterministic_checksum(assumptions)
    snap = GradingCandidateSnapshot(
        grading_candidate_id=int(row.id),
        assumptions_json=dict(assumptions),
        evidence_count=ec,
        checksum=checksum,
    )
    session.add(snap)
    session.flush()
    return snap


def emit_lifecycle(
    session: Session,
    *,
    grading_candidate_id: int,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    payload: dict[str, object] | None = None,
) -> None:
    session.add(
        GradingCandidateLifecycleEvent(
            grading_candidate_id=grading_candidate_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            payload_json=payload or {},
        )
    )


def latest_snapshot_checksum(session: Session, grading_candidate_id: int) -> str | None:
    stmt = (
        select(GradingCandidateSnapshot.checksum)
        .where(col(GradingCandidateSnapshot.grading_candidate_id) == grading_candidate_id)
        .order_by(
            col(GradingCandidateSnapshot.created_at).desc(), col(GradingCandidateSnapshot.id).desc()
        )
        .limit(1)
    )
    row = session.exec(stmt).first()
    return str(row) if row is not None else None


def coerce_candidate_read(session: Session, row: GradingCandidate) -> GradingCandidateRead:
    cid = int(row.id or 0)
    ec = evidence_count(session, cid)
    chk = latest_snapshot_checksum(session, cid)
    return GradingCandidateRead(
        id=cid,
        owner_user_id=int(row.owner_user_id),
        inventory_item_id=int(row.inventory_item_id),
        canonical_comic_issue_id=row.canonical_comic_issue_id,
        status=str(row.status),
        target_grader=str(row.target_grader),
        target_grade=row.target_grade,
        estimated_raw_value=row.estimated_raw_value,
        estimated_graded_value=row.estimated_graded_value,
        estimated_spread=row.estimated_spread,
        estimated_grading_cost=row.estimated_grading_cost,
        estimated_roi=row.estimated_roi,
        candidate_priority=str(row.candidate_priority),
        rationale=row.rationale,
        replay_key=row.replay_key,
        evidence_count=ec,
        latest_snapshot_checksum=chk,
        created_at=row.created_at,
        updated_at=row.updated_at,
        submitted_at=row.submitted_at,
        graded_at=row.graded_at,
        archived_at=row.archived_at,
    )


def _assert_inventory_owned(
    session: Session, *, owner_user_id: int, inventory_item_id: int
) -> InventoryCopy:
    inv = session.get(InventoryCopy, inventory_item_id)
    if inv is None or int(inv.user_id) != int(owner_user_id):
        raise HTTPException(status_code=404, detail="inventory item not found")
    return inv


def _assert_canonical_issue_exists(session: Session, issue_id: int | None) -> None:
    if issue_id is None:
        return
    if session.get(ComicIssue, issue_id) is None:
        raise HTTPException(status_code=400, detail="canonical comic issue not found")


def count_pipeline_active(session: Session, *, owner_user_id: int, inventory_item_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(GradingCandidate)
        .where(col(GradingCandidate.owner_user_id) == owner_user_id)
        .where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
        .where(col(GradingCandidate.status).in_(PIPELINE_STATUSES))
    )
    return int(session.exec(stmt).one())


def get_owner_candidate(
    session: Session, *, owner_user_id: int, candidate_id: int
) -> GradingCandidate:
    row = session.get(GradingCandidate, candidate_id)
    if row is None or int(row.owner_user_id) != int(owner_user_id):
        raise HTTPException(status_code=404, detail="grading candidate not found")
    return row


def get_ops_candidate(session: Session, candidate_id: int) -> GradingCandidate:
    row = session.get(GradingCandidate, candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="grading candidate not found")
    return row


def build_detail_read(session: Session, row: GradingCandidate) -> GradingCandidateDetailRead:
    cid = int(row.id or 0)
    ev_rows = session.exec(
        select(GradingCandidateEvidence)
        .where(col(GradingCandidateEvidence.grading_candidate_id) == cid)
        .order_by(
            col(GradingCandidateEvidence.created_at).asc(), col(GradingCandidateEvidence.id).asc()
        )
    ).all()
    lc_rows = session.exec(
        select(GradingCandidateLifecycleEvent)
        .where(col(GradingCandidateLifecycleEvent.grading_candidate_id) == cid)
        .order_by(
            col(GradingCandidateLifecycleEvent.created_at).asc(),
            col(GradingCandidateLifecycleEvent.id).asc(),
        )
    ).all()
    sn_rows = session.exec(
        select(GradingCandidateSnapshot)
        .where(col(GradingCandidateSnapshot.grading_candidate_id) == cid)
        .order_by(
            col(GradingCandidateSnapshot.created_at).asc(), col(GradingCandidateSnapshot.id).asc()
        )
    ).all()

    return GradingCandidateDetailRead(
        candidate=coerce_candidate_read(session, row),
        lifecycle_events=[
            GradingCandidateLifecycleEventRead(
                id=int(e.id),
                grading_candidate_id=int(e.grading_candidate_id),
                event_type=str(e.event_type),
                from_status=e.from_status,
                to_status=e.to_status,
                payload_json=dict(e.payload_json or {}),
                created_at=e.created_at,
            )
            for e in lc_rows
        ],
        snapshots=[
            GradingCandidateSnapshotRead(
                id=int(s.id),
                grading_candidate_id=int(s.grading_candidate_id),
                assumptions_json=dict(s.assumptions_json or {}),
                evidence_count=int(s.evidence_count),
                checksum=str(s.checksum),
                created_at=s.created_at,
            )
            for s in sn_rows
        ],
        evidence=[
            GradingCandidateEvidenceRead(
                id=int(ev.id),
                grading_candidate_id=int(ev.grading_candidate_id),
                evidence_type=str(ev.evidence_type),
                lineage_domain=str(ev.lineage_domain),
                lineage_key=str(ev.lineage_key),
                reference_json=dict(ev.reference_json or {}),
                created_at=ev.created_at,
            )
            for ev in ev_rows
        ],
    )


def create_candidate(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingCandidateCreatePayload,
) -> tuple[GradingCandidateDetailRead, bool]:
    replay_trim = payload.replay_key.strip() if payload.replay_key else None
    if replay_trim:
        existing = session.exec(
            select(GradingCandidate).where(
                col(GradingCandidate.owner_user_id) == owner_user_id,
                col(GradingCandidate.replay_key) == replay_trim,
            )
        ).first()
        if existing is not None:
            session.refresh(existing)
            return build_detail_read(session, existing), True

    _assert_inventory_owned(
        session, owner_user_id=owner_user_id, inventory_item_id=payload.inventory_item_id
    )
    _assert_canonical_issue_exists(session, payload.canonical_comic_issue_id)
    inv = session.get(InventoryCopy, payload.inventory_item_id)
    resolved_catalog_issue_id = effective_catalog_issue_id(
        session,
        catalog_issue_id=None,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
        inventory_copy_id=payload.inventory_item_id,
    )
    if inv is not None and inv.catalog_issue_id is not None and resolved_catalog_issue_id is None:
        resolved_catalog_issue_id = int(inv.catalog_issue_id)

    if payload.target_grader.upper() not in _GRADER_VALUES:
        raise HTTPException(status_code=400, detail="invalid target_grader")
    if payload.candidate_priority.upper() not in _PRIORITY_VALUES:
        raise HTTPException(status_code=400, detail="invalid candidate_priority")

    if (
        count_pipeline_active(
            session, owner_user_id=owner_user_id, inventory_item_id=payload.inventory_item_id
        )
        > 0
    ):
        raise HTTPException(
            status_code=409,
            detail="inventory item already has an active grading candidate in the pipeline",
        )

    row = GradingCandidate(
        owner_user_id=owner_user_id,
        inventory_item_id=payload.inventory_item_id,
        canonical_comic_issue_id=payload.canonical_comic_issue_id,
        catalog_issue_id=resolved_catalog_issue_id,
        status="CANDIDATE",
        target_grader=payload.target_grader.upper(),
        target_grade=payload.target_grade.strip() if payload.target_grade else None,
        estimated_raw_value=_money_quantize(payload.estimated_raw_value),
        estimated_graded_value=_money_quantize(payload.estimated_graded_value),
        estimated_spread=_money_quantize(payload.estimated_spread),
        estimated_grading_cost=_money_quantize(payload.estimated_grading_cost),
        estimated_roi=_roi_quantize(payload.estimated_roi),
        candidate_priority=payload.candidate_priority.upper(),
        rationale=payload.rationale.strip() if payload.rationale else None,
        replay_key=replay_trim,
        submitted_at=None,
        graded_at=None,
        archived_at=None,
    )
    session.add(row)
    session.flush()

    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="CREATED",
        from_status=None,
        to_status="CANDIDATE",
        payload={"replay_key": replay_trim},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row), False


def patch_candidate(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
    payload: GradingCandidatePatchPayload,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) not in _PATCHABLE_STATUSES:
        raise HTTPException(
            status_code=409, detail="grading candidate cannot be edited in this status"
        )

    changes: dict[str, object] = {}
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return build_detail_read(session, row)

    if "canonical_comic_issue_id" in data:
        _assert_canonical_issue_exists(session, data["canonical_comic_issue_id"])
        row.canonical_comic_issue_id = data["canonical_comic_issue_id"]
        changes["canonical_comic_issue_id"] = row.canonical_comic_issue_id
    if "target_grader" in data and data["target_grader"] is not None:
        tg = str(data["target_grader"]).upper()
        if tg not in _GRADER_VALUES:
            raise HTTPException(status_code=400, detail="invalid target_grader")
        row.target_grader = tg
        changes["target_grader"] = tg
    if "target_grade" in data:
        row.target_grade = data["target_grade"].strip() if data["target_grade"] else None
        changes["target_grade"] = row.target_grade
    if "estimated_raw_value" in data:
        row.estimated_raw_value = _money_quantize(data["estimated_raw_value"])
        changes["estimated_raw_value"] = _money_key(row.estimated_raw_value)
    if "estimated_graded_value" in data:
        row.estimated_graded_value = _money_quantize(data["estimated_graded_value"])
        changes["estimated_graded_value"] = _money_key(row.estimated_graded_value)
    if "estimated_spread" in data:
        row.estimated_spread = _money_quantize(data["estimated_spread"])
        changes["estimated_spread"] = _money_key(row.estimated_spread)
    if "estimated_grading_cost" in data:
        row.estimated_grading_cost = _money_quantize(data["estimated_grading_cost"])
        changes["estimated_grading_cost"] = _money_key(row.estimated_grading_cost)
    if "estimated_roi" in data:
        row.estimated_roi = _roi_quantize(data["estimated_roi"])
        changes["estimated_roi"] = _roi_key(row.estimated_roi)
    if "candidate_priority" in data and data["candidate_priority"] is not None:
        pr = str(data["candidate_priority"]).upper()
        if pr not in _PRIORITY_VALUES:
            raise HTTPException(status_code=400, detail="invalid candidate_priority")
        row.candidate_priority = pr
        changes["candidate_priority"] = pr
    if "rationale" in data:
        row.rationale = data["rationale"].strip() if data["rationale"] else None
        changes["rationale"] = row.rationale

    row.updated_at = utc_now()
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="UPDATED",
        from_status=str(row.status),
        to_status=str(row.status),
        payload={"changes": changes},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def append_evidence_row(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
    payload: GradingCandidateEvidenceCreatePayload,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) == "ARCHIVED":
        raise HTTPException(status_code=409, detail="grading candidate is archived")

    ev_type = str(payload.evidence_type).strip()
    ev = GradingCandidateEvidence(
        grading_candidate_id=int(row.id),
        evidence_type=ev_type.upper(),
        lineage_domain=payload.lineage_domain.strip(),
        lineage_key=payload.lineage_key.strip(),
        reference_json=dict(payload.reference_json or {}),
    )
    session.add(ev)
    row.updated_at = utc_now()
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="UPDATED",
        from_status=str(row.status),
        to_status=str(row.status),
        payload={
            "evidence_append": {"lineage_domain": ev.lineage_domain, "lineage_key": ev.lineage_key}
        },
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def transition_review(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) != "CANDIDATE":
        raise HTTPException(
            status_code=409, detail="candidate must be in CANDIDATE status to start review"
        )
    prev = str(row.status)
    row.status = "REVIEWING"
    row.updated_at = utc_now()
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="REVIEW_STARTED",
        from_status=prev,
        to_status=row.status,
        payload={},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def transition_ready(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) != "REVIEWING":
        raise HTTPException(status_code=409, detail="candidate must be in REVIEWING status")
    prev = str(row.status)
    row.status = "READY_FOR_SUBMISSION"
    row.updated_at = utc_now()
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="READY_FOR_SUBMISSION",
        from_status=prev,
        to_status=row.status,
        payload={},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def transition_submit(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) != "READY_FOR_SUBMISSION":
        raise HTTPException(status_code=409, detail="candidate must be READY_FOR_SUBMISSION")
    prev = str(row.status)
    now = utc_now()
    row.status = "SUBMITTED"
    row.submitted_at = now
    row.updated_at = now
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="SUBMITTED",
        from_status=prev,
        to_status=row.status,
        payload={},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def transition_grade(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
    payload: GradingCandidateGradePayload,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) != "SUBMITTED":
        raise HTTPException(
            status_code=409, detail="candidate must be SUBMITTED before grading completes"
        )
    prev = str(row.status)
    now = utc_now()
    row.status = "GRADED"
    row.graded_at = now
    row.updated_at = now
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="GRADED",
        from_status=prev,
        to_status=row.status,
        payload={"notes": payload.notes},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def transition_reject(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
    payload: GradingCandidateRejectPayload,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) not in {"CANDIDATE", "REVIEWING", "READY_FOR_SUBMISSION", "SUBMITTED"}:
        raise HTTPException(status_code=409, detail="candidate cannot be rejected from this status")
    prev = str(row.status)
    row.status = "REJECTED"
    row.updated_at = utc_now()
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="REJECTED",
        from_status=prev,
        to_status=row.status,
        payload={"reason": payload.reason},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def transition_archive(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> GradingCandidateDetailRead:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if str(row.status) == "ARCHIVED":
        raise HTTPException(status_code=409, detail="candidate already archived")
    prev = str(row.status)
    now = utc_now()
    row.status = "ARCHIVED"
    row.archived_at = now
    row.updated_at = now
    emit_lifecycle(
        session,
        grading_candidate_id=int(row.id),
        event_type="ARCHIVED",
        from_status=prev,
        to_status=row.status,
        payload={},
    )
    append_snapshot(session, row)
    session.commit()
    session.refresh(row)
    return build_detail_read(session, row)


def list_candidates_owner(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None,
    inventory_item_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingCandidate], int]:
    lim, off = clamp_grading_list_pagination(limit, offset)
    count_stmt = (
        select(func.count())
        .select_from(GradingCandidate)
        .where(
            col(GradingCandidate.owner_user_id) == owner_user_id,
        )
    )
    list_stmt = select(GradingCandidate).where(col(GradingCandidate.owner_user_id) == owner_user_id)
    if status:
        count_stmt = count_stmt.where(col(GradingCandidate.status) == status)
        list_stmt = list_stmt.where(col(GradingCandidate.status) == status)
    if inventory_item_id is not None:
        count_stmt = count_stmt.where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
        list_stmt = list_stmt.where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
    total = int(session.exec(count_stmt).one())
    rows = session.exec(
        list_stmt.order_by(col(GradingCandidate.updated_at).desc(), col(GradingCandidate.id).desc())
        .limit(lim)
        .offset(off)
    ).all()
    return list(rows), total


def list_candidates_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    status: str | None,
    inventory_item_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingCandidate], int]:
    lim, off = clamp_grading_list_pagination(limit, offset)
    count_stmt = select(func.count()).select_from(GradingCandidate)
    list_stmt = select(GradingCandidate)
    if owner_user_id is not None:
        count_stmt = count_stmt.where(col(GradingCandidate.owner_user_id) == owner_user_id)
        list_stmt = list_stmt.where(col(GradingCandidate.owner_user_id) == owner_user_id)
    if status:
        count_stmt = count_stmt.where(col(GradingCandidate.status) == status)
        list_stmt = list_stmt.where(col(GradingCandidate.status) == status)
    if inventory_item_id is not None:
        count_stmt = count_stmt.where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
        list_stmt = list_stmt.where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
    total = int(session.exec(count_stmt).one())
    rows = session.exec(
        list_stmt.order_by(col(GradingCandidate.updated_at).desc(), col(GradingCandidate.id).desc())
        .limit(lim)
        .offset(off)
    ).all()
    return list(rows), total


def list_response_from_rows(
    session: Session,
    *,
    rows: list[GradingCandidate],
    total: int,
    limit: int,
    offset: int,
) -> GradingCandidateListResponse:
    reads = [coerce_candidate_read(session, r) for r in rows]
    return GradingCandidateListResponse(items=reads, total_items=total, limit=limit, offset=offset)


def dashboard_summary_owner(
    session: Session, *, owner_user_id: int
) -> GradingCandidateDashboardSummary:
    base_own = select(GradingCandidate).where(col(GradingCandidate.owner_user_id) == owner_user_id)
    total = int(session.exec(select(func.count()).select_from(base_own.subquery())).one())
    pipe = int(
        session.exec(
            select(func.count())
            .select_from(GradingCandidate)
            .where(col(GradingCandidate.owner_user_id) == owner_user_id)
            .where(col(GradingCandidate.status).in_(PIPELINE_STATUSES))
        ).one()
    )
    ready = int(
        session.exec(
            select(func.count())
            .select_from(GradingCandidate)
            .where(col(GradingCandidate.owner_user_id) == owner_user_id)
            .where(col(GradingCandidate.status) == "READY_FOR_SUBMISSION")
        ).one()
    )
    submitted = int(
        session.exec(
            select(func.count())
            .select_from(GradingCandidate)
            .where(col(GradingCandidate.owner_user_id) == owner_user_id)
            .where(col(GradingCandidate.status) == "SUBMITTED")
        ).one()
    )
    graded = int(
        session.exec(
            select(func.count())
            .select_from(GradingCandidate)
            .where(col(GradingCandidate.owner_user_id) == owner_user_id)
            .where(col(GradingCandidate.status) == "GRADED")
        ).one()
    )
    elite = int(
        session.exec(
            select(func.count())
            .select_from(GradingCandidate)
            .where(col(GradingCandidate.owner_user_id) == owner_user_id)
            .where(col(GradingCandidate.candidate_priority) == "ELITE")
            .where(col(GradingCandidate.status) != "ARCHIVED")
        ).one()
    )
    return GradingCandidateDashboardSummary(
        total_candidates=total,
        pipeline_active_count=pipe,
        ready_for_submission_count=ready,
        submitted_count=submitted,
        graded_count=graded,
        elite_priority_count=elite,
    )


def list_lifecycle_events_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    limit: int,
    offset: int,
) -> GradingCandidateLifecycleEventListResponse:
    lim, off = clamp_grading_list_pagination(limit, offset)
    base = select(GradingCandidateLifecycleEvent)
    if grading_candidate_id is not None:
        base = base.where(
            col(GradingCandidateLifecycleEvent.grading_candidate_id) == grading_candidate_id
        )
    if owner_user_id is not None:
        cand_ids = session.exec(
            select(GradingCandidate.id).where(col(GradingCandidate.owner_user_id) == owner_user_id)
        ).all()
        id_list = [int(i) for i in cand_ids if i is not None]
        if not id_list:
            return GradingCandidateLifecycleEventListResponse(
                items=[], total_items=0, limit=lim, offset=off
            )
        base = base.where(col(GradingCandidateLifecycleEvent.grading_candidate_id).in_(id_list))
    cnt = int(session.exec(select(func.count()).select_from(base.subquery())).one())
    rows = session.exec(
        base.order_by(
            col(GradingCandidateLifecycleEvent.created_at).desc(),
            col(GradingCandidateLifecycleEvent.id).desc(),
        )
        .limit(lim)
        .offset(off)
    ).all()
    reads = [
        GradingCandidateLifecycleEventRead(
            id=int(r.id),
            grading_candidate_id=int(r.grading_candidate_id),
            event_type=str(r.event_type),
            from_status=r.from_status,
            to_status=r.to_status,
            payload_json=dict(r.payload_json or {}),
            created_at=r.created_at,
        )
        for r in rows
    ]
    return GradingCandidateLifecycleEventListResponse(
        items=reads, total_items=cnt, limit=lim, offset=off
    )


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    limit: int,
    offset: int,
) -> GradingCandidateEvidenceListResponse:
    lim, off = clamp_grading_list_pagination(limit, offset)
    base = select(GradingCandidateEvidence)
    if grading_candidate_id is not None:
        base = base.where(
            col(GradingCandidateEvidence.grading_candidate_id) == grading_candidate_id
        )
    if owner_user_id is not None:
        cand_ids = session.exec(
            select(GradingCandidate.id).where(col(GradingCandidate.owner_user_id) == owner_user_id)
        ).all()
        id_list = [int(i) for i in cand_ids if i is not None]
        if not id_list:
            return GradingCandidateEvidenceListResponse(
                items=[], total_items=0, limit=lim, offset=off
            )
        base = base.where(col(GradingCandidateEvidence.grading_candidate_id).in_(id_list))
    cnt = int(session.exec(select(func.count()).select_from(base.subquery())).one())
    rows = session.exec(
        base.order_by(
            col(GradingCandidateEvidence.created_at).desc(), col(GradingCandidateEvidence.id).desc()
        )
        .limit(lim)
        .offset(off)
    ).all()
    reads = [
        GradingCandidateEvidenceRead(
            id=int(r.id),
            grading_candidate_id=int(r.grading_candidate_id),
            evidence_type=str(r.evidence_type),
            lineage_domain=str(r.lineage_domain),
            lineage_key=str(r.lineage_key),
            reference_json=dict(r.reference_json or {}),
            created_at=r.created_at,
        )
        for r in rows
    ]
    return GradingCandidateEvidenceListResponse(items=reads, total_items=cnt, limit=lim, offset=off)


def inventory_grading_badge(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryGradingCandidateBadge | None:
    active = session.exec(
        select(GradingCandidate)
        .where(col(GradingCandidate.owner_user_id) == owner_user_id)
        .where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
        .where(col(GradingCandidate.status).in_(PIPELINE_STATUSES))
        .order_by(col(GradingCandidate.id).desc())
    ).first()
    if active is not None:
        return InventoryGradingCandidateBadge(
            grading_candidate_id=int(active.id),
            status=str(active.status),
            target_grader=str(active.target_grader),
            candidate_priority=str(active.candidate_priority),
            is_pipeline_active=True,
        )
    hist = session.exec(
        select(GradingCandidate)
        .where(col(GradingCandidate.owner_user_id) == owner_user_id)
        .where(col(GradingCandidate.inventory_item_id) == inventory_item_id)
        .where(col(GradingCandidate.status) != "ARCHIVED")
        .order_by(col(GradingCandidate.id).desc())
    ).first()
    if hist is None:
        return None
    return InventoryGradingCandidateBadge(
        grading_candidate_id=int(hist.id),
        status=str(hist.status),
        target_grader=str(hist.target_grader),
        candidate_priority=str(hist.candidate_priority),
        is_pipeline_active=False,
    )
