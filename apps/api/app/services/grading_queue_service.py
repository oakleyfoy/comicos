"""P72-02 grading operations queue."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.models import InventoryCopy
from app.models.p72_grading_operations import (
    P72GradingQueueEntry,
    P72InventoryGradingHistory,
)
from app.schemas.p72_grading_operations import (
    P72GradingQueueEnqueuePayload,
    P72GradingQueueEntryRead,
    P72GradingQueueListResponse,
    P72GradingQueueStatusPayload,
)
from app.services.grading_audit_log import append_grading_audit_log
from app.services.sell_candidate_engine import _split_identity_key

STATUS_CANDIDATE = "CANDIDATE"
STATUS_READY = "READY_TO_SUBMIT"
STATUS_SUBMITTED = "SUBMITTED"
STATUS_AT_CGC = "AT_CGC"
STATUS_GRADING_COMPLETE = "GRADING_COMPLETE"
STATUS_RETURNED = "RETURNED"
STATUS_LISTED = "LISTED"
STATUS_SOLD = "SOLD"

ALL_STATUSES = frozenset(
    {
        STATUS_CANDIDATE,
        STATUS_READY,
        STATUS_SUBMITTED,
        STATUS_AT_CGC,
        STATUS_GRADING_COMPLETE,
        STATUS_RETURNED,
        STATUS_LISTED,
        STATUS_SOLD,
    }
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_CANDIDATE: frozenset({STATUS_READY}),
    STATUS_READY: frozenset({STATUS_SUBMITTED, STATUS_CANDIDATE}),
    STATUS_SUBMITTED: frozenset({STATUS_AT_CGC, STATUS_READY}),
    STATUS_AT_CGC: frozenset({STATUS_GRADING_COMPLETE}),
    STATUS_GRADING_COMPLETE: frozenset({STATUS_RETURNED}),
    STATUS_RETURNED: frozenset({STATUS_LISTED}),
    STATUS_LISTED: frozenset({STATUS_SOLD}),
    STATUS_SOLD: frozenset(),
}

WAITING_STATUSES = frozenset({STATUS_CANDIDATE, STATUS_READY})
IN_PROCESS_STATUSES = frozenset({STATUS_SUBMITTED, STATUS_AT_CGC, STATUS_GRADING_COMPLETE})
COMPLETED_STATUSES = frozenset({STATUS_RETURNED, STATUS_LISTED, STATUS_SOLD})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _search_blob(*, title: str, publisher: str, issue: str, copy_id: int) -> str:
    return f"{title} {publisher} {issue} {copy_id}".lower()[:512]


def _entry_read(row: P72GradingQueueEntry) -> P72GradingQueueEntryRead:
    return P72GradingQueueEntryRead.model_validate(row)


def _get_copy(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> InventoryCopy:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Inventory copy not found.")
    return copy


def _title_fields(copy: InventoryCopy) -> tuple[str, str, str]:
    pub, series, issue, _ = _split_identity_key(copy.metadata_identity_key)
    title = series or (copy.metadata_identity_key or f"Copy {copy.id}")
    return title, pub, issue


def enqueue_queue_entries(
    session: Session,
    *,
    owner_user_id: int,
    payload: P72GradingQueueEnqueuePayload,
    created_by_user_id: int | None = None,
) -> list[P72GradingQueueEntryRead]:
    created: list[P72GradingQueueEntryRead] = []
    for copy_id in payload.inventory_copy_ids:
        existing = session.exec(
            select(P72GradingQueueEntry)
            .where(P72GradingQueueEntry.owner_user_id == owner_user_id)
            .where(P72GradingQueueEntry.inventory_copy_id == copy_id)
            .where(col(P72GradingQueueEntry.status).notin_([STATUS_SOLD]))
        ).first()
        if existing is not None:
            created.append(_entry_read(existing))
            continue
        copy = _get_copy(session, owner_user_id=owner_user_id, inventory_copy_id=copy_id)
        title, pub, issue = _title_fields(copy)
        row = P72GradingQueueEntry(
            owner_user_id=owner_user_id,
            inventory_copy_id=copy_id,
            status=STATUS_CANDIDATE,
            target_grader=payload.target_grader.upper(),
            title=title[:256],
            publisher=pub[:80],
            issue_number=issue[:32],
            estimated_grading_cost=payload.estimated_grading_cost,
            search_blob=_search_blob(title=title, publisher=pub, issue=issue, copy_id=copy_id),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(row)
        session.flush()
        append_grading_audit_log(
            session,
            owner_user_id=owner_user_id,
            queue_entry_id=int(row.id or 0),
            event_type="ENQUEUED",
            prior_status=None,
            new_status=STATUS_CANDIDATE,
            created_by_user_id=created_by_user_id,
        )
        created.append(_entry_read(row))
    session.commit()
    for row in created:
        try:
            from app.services.recommendation_outcome_service import record_automatic_event_for_inventory

            record_automatic_event_for_inventory(
                session,
                owner_user_id=owner_user_id,
                inventory_copy_id=row.inventory_copy_id,
                event_type="GRADED",
                event_source="grading_queue_enqueue",
                metadata_json={"queue_entry_id": row.id},
            )
        except Exception:
            pass
    return created


def list_queue_entries(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    batch_id: int | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> P72GradingQueueListResponse:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    q = select(P72GradingQueueEntry).where(P72GradingQueueEntry.owner_user_id == owner_user_id)
    if status:
        q = q.where(P72GradingQueueEntry.status == status.upper())
    if batch_id is not None:
        q = q.where(P72GradingQueueEntry.p72_grading_batch_id == batch_id)
    if search:
        needle = search.lower().strip()
        q = q.where(col(P72GradingQueueEntry.search_blob).contains(needle))
    rows = list(session.exec(q.order_by(P72GradingQueueEntry.updated_at.desc())).all())
    page = rows[offset : offset + limit]
    return P72GradingQueueListResponse(
        items=[_entry_read(r) for r in page],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def _days_between(start: date | None, end: date | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, (end - start).days)


def _apply_return_processing(
    session: Session,
    *,
    owner_user_id: int,
    entry: P72GradingQueueEntry,
    payload: P72GradingQueueStatusPayload,
) -> None:
    if not payload.actual_grade:
        raise HTTPException(status_code=400, detail="actual_grade is required when marking RETURNED.")
    entry.actual_grade = payload.actual_grade
    entry.certification_number = payload.certification_number
    entry.slab_notes = payload.slab_notes
    entry.final_grading_cost = payload.final_grading_cost
    copy = session.get(InventoryCopy, entry.inventory_copy_id)
    if copy is not None and copy.user_id == owner_user_id:
        copy.grade_status = f"graded_{payload.actual_grade}".replace(".", "_")[:50]
        session.add(copy)
    session.add(
        P72InventoryGradingHistory(
            owner_user_id=owner_user_id,
            inventory_copy_id=entry.inventory_copy_id,
            queue_entry_id=int(entry.id or 0),
            actual_grade=payload.actual_grade,
            certification_number=payload.certification_number,
            slab_notes=payload.slab_notes,
            final_grading_cost=payload.final_grading_cost,
            target_grader=entry.target_grader,
            created_at=utc_now(),
        )
    )


def update_queue_status(
    session: Session,
    *,
    owner_user_id: int,
    queue_entry_id: int,
    payload: P72GradingQueueStatusPayload,
    created_by_user_id: int | None = None,
) -> P72GradingQueueEntryRead:
    entry = session.get(P72GradingQueueEntry, queue_entry_id)
    if entry is None or entry.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Queue entry not found.")
    new_status = str(payload.status).upper()
    if new_status not in ALL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    prior = entry.status
    allowed = ALLOWED_TRANSITIONS.get(prior, frozenset())
    if new_status != prior and new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {prior} to {new_status}.",
        )
    if payload.submission_date:
        entry.submission_date = payload.submission_date
    if payload.received_date:
        entry.received_date = payload.received_date
    if payload.estimated_completion_date:
        entry.estimated_completion_date = payload.estimated_completion_date
    if payload.actual_completion_date:
        entry.actual_completion_date = payload.actual_completion_date
    return_payload = payload if new_status == STATUS_RETURNED else None
    if new_status == STATUS_RETURNED:
        from app.services.grading_outcome_service import record_outcome_for_queue_entry

        record_outcome_for_queue_entry(
            session,
            owner_user_id=owner_user_id,
            entry=entry,
            queue_status=new_status,
            final_grading_cost=payload.final_grading_cost,
            actual_grade=payload.actual_grade,
        )
        _apply_return_processing(
            session,
            owner_user_id=owner_user_id,
            entry=entry,
            payload=payload,
        )
    entry.status = new_status
    entry.turnaround_days = _days_between(entry.submission_date, entry.actual_completion_date or date.today())
    entry.updated_at = utc_now()
    session.add(entry)
    append_grading_audit_log(
        session,
        owner_user_id=owner_user_id,
        queue_entry_id=queue_entry_id,
        event_type="STATUS_CHANGE",
        prior_status=prior,
        new_status=new_status,
        created_by_user_id=created_by_user_id,
        metadata_json={"payload": payload.model_dump(mode="json")},
    )
    if new_status in COMPLETED_STATUSES and entry.actual_grade and new_status != STATUS_RETURNED:
        from app.services.grading_outcome_service import record_outcome_for_queue_entry

        record_outcome_for_queue_entry(
            session,
            owner_user_id=owner_user_id,
            entry=entry,
            queue_status=new_status,
        )
    session.commit()
    session.refresh(entry)
    if new_status in {STATUS_LISTED, STATUS_SOLD}:
        try:
            from app.services.recommendation_outcome_service import record_automatic_event_for_inventory

            record_automatic_event_for_inventory(
                session,
                owner_user_id=owner_user_id,
                inventory_copy_id=entry.inventory_copy_id,
                event_type=new_status,
                event_source="grading_queue_status",
                metadata_json={"queue_entry_id": queue_entry_id},
            )
        except Exception:
            pass
    return _entry_read(entry)


def get_queue_entry(
    session: Session,
    *,
    owner_user_id: int,
    queue_entry_id: int,
) -> P72GradingQueueEntryRead | None:
    entry = session.get(P72GradingQueueEntry, queue_entry_id)
    if entry is None or entry.owner_user_id != owner_user_id:
        return None
    return _entry_read(entry)
