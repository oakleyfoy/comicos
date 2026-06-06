"""P72-02 submission batch management (operational; no CGC API)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models.p72_grading_operations import P72GradingBatch, P72GradingQueueEntry
from app.schemas.p72_grading_operations import (
    P72GradingBatchAssignPayload,
    P72GradingBatchCreatePayload,
    P72GradingBatchListResponse,
    P72GradingBatchRead,
)
from app.services.grading_audit_log import append_grading_audit_log
from app.services.grading_queue_service import (
    STATUS_READY,
    STATUS_SUBMITTED,
    update_queue_status,
)
from app.schemas.p72_grading_operations import P72GradingQueueStatusPayload

DEFAULT_TURNAROUND_DAYS = 90


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _batch_read(row: P72GradingBatch) -> P72GradingBatchRead:
    return P72GradingBatchRead.model_validate(row)


def _refresh_batch_counts(session: Session, batch: P72GradingBatch) -> None:
    count = session.exec(
        select(func.count())
        .select_from(P72GradingQueueEntry)
        .where(P72GradingQueueEntry.p72_grading_batch_id == batch.id)
    ).one()
    batch.book_count = int(count or 0)
    batch.updated_at = utc_now()


def create_batch(
    session: Session,
    *,
    owner_user_id: int,
    payload: P72GradingBatchCreatePayload,
    created_by_user_id: int | None = None,
) -> P72GradingBatchRead:
    sub_date = payload.submission_date or date.today()
    est_complete = sub_date + timedelta(days=DEFAULT_TURNAROUND_DAYS)
    batch = P72GradingBatch(
        owner_user_id=owner_user_id,
        batch_name=payload.batch_name.strip(),
        target_grader=payload.target_grader.upper(),
        submission_date=sub_date,
        estimated_cost=payload.estimated_cost,
        estimated_completion_date=est_complete,
        batch_status="OPEN",
        notes=payload.notes,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(batch)
    session.flush()
    if payload.queue_entry_ids:
        assign_entries_to_batch(
            session,
            owner_user_id=owner_user_id,
            batch_id=int(batch.id or 0),
            payload=P72GradingBatchAssignPayload(queue_entry_ids=payload.queue_entry_ids),
            created_by_user_id=created_by_user_id,
        )
    else:
        session.commit()
    session.refresh(batch)
    _refresh_batch_counts(session, batch)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return _batch_read(batch)


def list_batches(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> P72GradingBatchListResponse:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = list(
        session.exec(
            select(P72GradingBatch)
            .where(P72GradingBatch.owner_user_id == owner_user_id)
            .order_by(P72GradingBatch.created_at.desc(), P72GradingBatch.id.desc())
        ).all()
    )
    page = rows[offset : offset + limit]
    return P72GradingBatchListResponse(
        items=[_batch_read(r) for r in page],
        total_items=len(rows),
        limit=limit,
        offset=offset,
    )


def assign_entries_to_batch(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
    payload: P72GradingBatchAssignPayload,
    created_by_user_id: int | None = None,
) -> P72GradingBatchRead:
    batch = session.get(P72GradingBatch, batch_id)
    if batch is None or batch.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Batch not found.")
    if payload.move_from_batch_id is not None:
        other = session.get(P72GradingBatch, payload.move_from_batch_id)
        if other is None or other.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="Source batch not found.")
    for qid in payload.queue_entry_ids:
        entry = session.get(P72GradingQueueEntry, qid)
        if entry is None or entry.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail=f"Queue entry {qid} not found.")
        if payload.move_from_batch_id and entry.p72_grading_batch_id != payload.move_from_batch_id:
            raise HTTPException(status_code=400, detail=f"Entry {qid} is not in the source batch.")
        prior_batch = entry.p72_grading_batch_id
        entry.p72_grading_batch_id = batch_id
        entry.target_grader = batch.target_grader
        entry.submission_date = batch.submission_date
        entry.estimated_completion_date = batch.estimated_completion_date
        if entry.status in {"CANDIDATE", STATUS_READY}:
            entry.status = STATUS_READY
        entry.updated_at = utc_now()
        session.add(entry)
        append_grading_audit_log(
            session,
            owner_user_id=owner_user_id,
            queue_entry_id=qid,
            event_type="BATCH_ASSIGN",
            prior_status=entry.status,
            new_status=entry.status,
            created_by_user_id=created_by_user_id,
            metadata_json={"batch_id": batch_id, "prior_batch_id": prior_batch},
        )
    _refresh_batch_counts(session, batch)
    if payload.move_from_batch_id:
        src = session.get(P72GradingBatch, payload.move_from_batch_id)
        if src:
            _refresh_batch_counts(session, src)
            session.add(src)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return _batch_read(batch)


def mark_batch_submitted(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
    created_by_user_id: int | None = None,
) -> P72GradingBatchRead:
    batch = session.get(P72GradingBatch, batch_id)
    if batch is None or batch.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Batch not found.")
    entries = session.exec(
        select(P72GradingQueueEntry).where(P72GradingQueueEntry.p72_grading_batch_id == batch_id)
    ).all()
    for entry in entries:
        if entry.status == STATUS_READY:
            update_queue_status(
                session,
                owner_user_id=owner_user_id,
                queue_entry_id=int(entry.id or 0),
                payload=P72GradingQueueStatusPayload(status=STATUS_SUBMITTED, submission_date=batch.submission_date),
                created_by_user_id=created_by_user_id,
            )
    batch.batch_status = "SUBMITTED"
    batch.updated_at = utc_now()
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return _batch_read(batch)
