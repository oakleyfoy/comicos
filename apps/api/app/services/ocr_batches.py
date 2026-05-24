from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import CoverImage, OcrBatch, OcrBatchItem, User
from app.core.config import get_settings
from app.schemas.ocr_batches import OcrBatchCreatePayload, OcrBatchItemRead, OcrBatchRead
from app.services.cover_images import (
    create_pending_cover_image_ocr_result,
    get_cover_entity_for_processing_by_ops_or_404,
    get_cover_entity_for_processing_by_owner,
)
from app.services.metadata_audits import record_metadata_audit
from app.services.ops_events import record_ops_event
from app.services.processing_errors import (
    ERROR_CODE_retry_exhausted,
    dumps_structured_error,
)
from app.tasks.queue import COVER_IMAGE_OCR_JOB_ID_TEMPLATE, enqueue_cover_image_ocr_job, fetch_job_by_id

BATCH_OCR_EXTRACTION_VERSION = "ocr-batch-orchestration-v1"
ACTIVE_RQ_STATUSES = {"queued", "started", "scheduled", "deferred"}
TERMINAL_BATCH_ITEM_STATUSES = {"completed", "failed", "skipped", "cancelled"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ocr_batch_item_entity_to_read(row: OcrBatchItem) -> OcrBatchItemRead:
    if row.id is None:
        raise ValueError("OCR batch item must be flushed before serialization")
    return OcrBatchItemRead(
        id=row.id,
        batch_id=row.batch_id,
        cover_image_id=row.cover_image_id,
        status=row.status,  # type: ignore[arg-type]
        job_id=row.job_id,
        attempt_count=row.attempt_count,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _ocr_batch_snapshot_public(batch: OcrBatch) -> dict[str, object]:
    return {
        "batch_key": batch.batch_key,
        "status": batch.status,
        "total_items": batch.total_items,
        "pending_count": batch.pending_count,
        "running_count": batch.running_count,
        "completed_count": batch.completed_count,
        "failed_count": batch.failed_count,
        "skipped_count": batch.skipped_count,
        "created_by": batch.created_by,
        "started_at": batch.started_at.isoformat() if batch.started_at is not None else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at is not None else None,
        "extraction_version": batch.extraction_version,
        "batch_options_json": batch.batch_options_json or {},
    }


def ocr_batch_entity_to_read(session: Session, batch: OcrBatch) -> OcrBatchRead:
    if batch.id is None:
        raise ValueError("OCR batch must be flushed before serialization")
    items = session.exec(
        select(OcrBatchItem)
        .where(OcrBatchItem.batch_id == batch.id)
        .order_by(OcrBatchItem.cover_image_id.asc(), OcrBatchItem.id.asc())
    ).all()
    return OcrBatchRead(
        id=batch.id,
        batch_key=batch.batch_key,
        status=batch.status,  # type: ignore[arg-type]
        total_items=batch.total_items,
        pending_count=batch.pending_count,
        running_count=batch.running_count,
        completed_count=batch.completed_count,
        failed_count=batch.failed_count,
        skipped_count=batch.skipped_count,
        created_by=batch.created_by,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        started_at=batch.started_at,
        completed_at=batch.completed_at,
        extraction_version=batch.extraction_version,
        batch_options_json=batch.batch_options_json or {},
        items=[ocr_batch_item_entity_to_read(item) for item in items],
    )


def _ocr_batch_event_for_status(status_value: str) -> str | None:
    return {
        "running": "ocr_batch_started",
        "completed": "ocr_batch_completed",
        "completed_with_errors": "ocr_batch_completed_with_errors",
        "failed": "ocr_batch_failed",
        "cancelled": "ocr_batch_cancelled",
    }.get(status_value)


def _extract_job_error(job) -> str | None:
    exc_info = getattr(job, "exc_info", None)
    if not exc_info:
        return None
    lines = [line.strip() for line in str(exc_info).splitlines() if line.strip()]
    if not lines:
        return "Job failed"
    return lines[-1][:2000]


def _set_item_status(
    session: Session,
    *,
    item: OcrBatchItem,
    status_value: Literal["queued", "running", "completed", "failed", "skipped", "cancelled"],
    job_id: str | None = None,
    error_message: str | None = None,
    actor_user_id: int | None = None,
) -> None:
    if item.id is None:
        raise ValueError("OCR batch item must be flushed before updates")
    if (
        item.status == status_value
        and item.job_id == (job_id if job_id is not None else item.job_id)
        and (error_message or item.last_error) == item.last_error
    ):
        return
    before = ocr_batch_item_entity_to_read(item)
    now = _now()
    item.status = status_value
    if job_id is not None:
        item.job_id = job_id
    if status_value in {"queued", "running"}:
        item.started_at = item.started_at or now
        item.completed_at = None
    elif status_value in TERMINAL_BATCH_ITEM_STATUSES:
        item.completed_at = now
    if status_value in {"completed", "queued", "running"}:
        item.last_error = None if error_message is None else error_message[:2000]
    else:
        item.last_error = error_message[:2000] if error_message else item.last_error
    item.updated_at = now
    session.add(item)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="ocr_batch_item",
        entity_id=item.id,
        action=f"ocr_batch_item_{status_value}",
        before_snapshot=before.model_dump(),
        after_snapshot=ocr_batch_item_entity_to_read(item).model_dump(),
        actor_user_id=actor_user_id,
    )


def _derive_batch_status(batch: OcrBatch, items: list[OcrBatchItem]) -> str:
    if batch.status == "cancelled":
        return "cancelled"
    if not items:
        return "failed"
    counts = Counter(item.status for item in items)
    pending_like = counts.get("pending", 0) + counts.get("queued", 0)
    running = counts.get("running", 0)
    completed = counts.get("completed", 0)
    failed = counts.get("failed", 0)
    skipped = counts.get("skipped", 0)
    terminal_total = completed + failed + skipped + counts.get("cancelled", 0)
    if pending_like > 0 or running > 0:
        return "running" if any(item.attempt_count > 0 for item in items) else "pending"
    if failed == len(items):
        return "failed"
    if completed == len(items):
        return "completed"
    if terminal_total == len(items) and (failed > 0 or skipped > 0):
        return "completed_with_errors"
    return "pending"


def _refresh_batch_summary(
    session: Session,
    batch: OcrBatch,
    *,
    actor_user_id: int | None = None,
) -> OcrBatch:
    if batch.id is None:
        raise ValueError("OCR batch must be flushed before summary refresh")
    items = session.exec(
        select(OcrBatchItem).where(OcrBatchItem.batch_id == batch.id).order_by(OcrBatchItem.id.asc())
    ).all()
    counts = Counter(item.status for item in items)
    before = _ocr_batch_snapshot_public(batch)
    batch.total_items = len(items)
    batch.pending_count = counts.get("pending", 0) + counts.get("queued", 0)
    batch.running_count = counts.get("running", 0)
    batch.completed_count = counts.get("completed", 0)
    batch.failed_count = counts.get("failed", 0)
    batch.skipped_count = counts.get("skipped", 0)

    any_started = any(item.attempt_count > 0 or item.status in {"running", "completed", "failed"} for item in items)
    if any_started and batch.started_at is None:
        batch.started_at = _now()

    next_status = _derive_batch_status(batch, items)
    status_changed = batch.status != next_status
    batch.status = next_status
    terminal_statuses = {"completed", "completed_with_errors", "failed", "cancelled"}
    if batch.status in terminal_statuses:
        if batch.completed_at is None or status_changed:
            batch.completed_at = _now()
    else:
        batch.completed_at = None
    batch.updated_at = _now()
    session.add(batch)
    session.flush()

    if status_changed:
        event = _ocr_batch_event_for_status(batch.status)
        if event:
            record_metadata_audit(
                session,
                entity_type="ocr_batch",
                entity_id=batch.id,
                action=event,
                before_snapshot=before,
                after_snapshot=_ocr_batch_snapshot_public(batch),
                actor_user_id=actor_user_id,
            )
    return batch


def _sync_item_runtime_state(session: Session, item: OcrBatchItem) -> None:
    if item.status not in {"queued", "running"} or not item.job_id:
        return
    job = fetch_job_by_id(item.job_id)
    if job is None:
        return
    status = job.get_status(refresh=True)
    if status in {"queued", "scheduled", "deferred"} and item.status != "queued":
        item.status = "queued"
        item.updated_at = _now()
        session.add(item)
    elif status == "started" and item.status != "running":
        item.status = "running"
        item.started_at = item.started_at or _now()
        item.updated_at = _now()
        session.add(item)
    elif status == "failed":
        _set_item_status(
            session,
            item=item,
            status_value="failed",
            error_message=_extract_job_error(job) or "OCR batch item failed",
        )


def _sync_batch_runtime_state(session: Session, batch: OcrBatch) -> OcrBatch:
    if batch.id is None:
        return batch
    items = session.exec(select(OcrBatchItem).where(OcrBatchItem.batch_id == batch.id)).all()
    changed = False
    for item in items:
        before = (item.status, item.started_at, item.updated_at, item.last_error)
        _sync_item_runtime_state(session, item)
        after = (item.status, item.started_at, item.updated_at, item.last_error)
        if before != after:
            changed = True
    _refresh_batch_summary(session, batch)
    if changed:
        session.commit()
        session.refresh(batch)
    return batch


def _list_batches_stmt(*, created_by: int | None = None, limit: int = 25):
    stmt = select(OcrBatch)
    if created_by is not None:
        stmt = stmt.where(OcrBatch.created_by == created_by)
    return stmt.order_by(OcrBatch.created_at.desc(), OcrBatch.id.desc()).limit(max(1, min(limit, 100)))


def get_ocr_batch_for_owner_or_404(session: Session, *, current_user: User, batch_id: int) -> OcrBatch:
    batch = session.get(OcrBatch, batch_id)
    if batch is None or batch.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="OCR batch not found")
    return batch


def get_ocr_batch_for_ops_or_404(session: Session, *, batch_id: int) -> OcrBatch:
    batch = session.get(OcrBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="OCR batch not found")
    return batch


def _normalized_cover_ids(ids: list[int]) -> tuple[list[int], list[int]]:
    numeric = [int(value) for value in ids if int(value) > 0]
    counts = Counter(numeric)
    duplicates = sorted([cover_id for cover_id, count in counts.items() if count > 1])
    return sorted(counts), duplicates


def _validate_cover_ids_for_owner(session: Session, *, current_user: User, cover_ids: list[int]) -> tuple[list[int], list[int]]:
    valid: list[int] = []
    invalid: list[int] = []
    for cover_id in cover_ids:
        try:
            get_cover_entity_for_processing_by_owner(session, current_user=current_user, cover_image_id=cover_id)
        except HTTPException:
            invalid.append(cover_id)
            continue
        valid.append(cover_id)
    return valid, invalid


def _validate_cover_ids_for_ops(session: Session, *, cover_ids: list[int]) -> tuple[list[int], list[int]]:
    valid: list[int] = []
    invalid: list[int] = []
    for cover_id in cover_ids:
        try:
            get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_id)
        except HTTPException:
            invalid.append(cover_id)
            continue
        valid.append(cover_id)
    return valid, invalid


def _create_ocr_batch(
    session: Session,
    *,
    actor_user_id: int | None,
    cover_ids: list[int],
    invalid_cover_ids: list[int],
    duplicate_cover_ids: list[int],
    batch_options_json: dict,
) -> OcrBatchRead:
    settings = get_settings()
    max_items = int(settings.cover_ocr_batch_max_items)
    if len(cover_ids) > max_items:
        raise HTTPException(
            status_code=422,
            detail=f"OCR batch exceeds maximum item count ({max_items}).",
        )
    now = _now()
    batch = OcrBatch(
        batch_key=f"pending-{int(now.timestamp() * 1000000)}-{actor_user_id or 0}",
        status="pending",
        total_items=len(cover_ids),
        pending_count=len(cover_ids),
        running_count=0,
        completed_count=0,
        failed_count=0,
        skipped_count=0,
        created_by=actor_user_id,
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
        extraction_version=BATCH_OCR_EXTRACTION_VERSION,
        batch_options_json={
            **batch_options_json,
            "requested_cover_image_ids": cover_ids,
            "invalid_cover_image_ids": invalid_cover_ids,
            "duplicate_cover_image_ids": duplicate_cover_ids,
        },
    )
    session.add(batch)
    session.flush()
    if batch.id is None:
        raise ValueError("Failed to create OCR batch")
    batch.batch_key = f"ocr-batch-{batch.id}"
    session.add(batch)
    session.flush()
    for cover_id in cover_ids:
        session.add(
            OcrBatchItem(
                batch_id=batch.id,
                cover_image_id=cover_id,
                status="pending",
                job_id=None,
                attempt_count=0,
                last_error=None,
                created_at=now,
                updated_at=now,
                started_at=None,
                completed_at=None,
            )
        )
    session.flush()
    _refresh_batch_summary(session, batch, actor_user_id=actor_user_id)
    record_metadata_audit(
        session,
        entity_type="ocr_batch",
        entity_id=batch.id,
        action="ocr_batch_created",
        before_snapshot=None,
        after_snapshot=_ocr_batch_snapshot_public(batch),
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(batch)
    return ocr_batch_entity_to_read(session, batch)


def create_ocr_batch_for_owner(
    session: Session,
    *,
    current_user: User,
    payload: OcrBatchCreatePayload,
) -> OcrBatchRead:
    normalized_ids, duplicate_cover_ids = _normalized_cover_ids(payload.cover_image_ids)
    valid_cover_ids, invalid_cover_ids = _validate_cover_ids_for_owner(
        session,
        current_user=current_user,
        cover_ids=normalized_ids,
    )
    return _create_ocr_batch(
        session,
        actor_user_id=current_user.id,
        cover_ids=valid_cover_ids,
        invalid_cover_ids=invalid_cover_ids,
        duplicate_cover_ids=duplicate_cover_ids,
        batch_options_json=payload.batch_options_json,
    )


def create_ocr_batch_for_ops(
    session: Session,
    *,
    actor_user_id: int | None,
    payload: OcrBatchCreatePayload,
) -> OcrBatchRead:
    normalized_ids, duplicate_cover_ids = _normalized_cover_ids(payload.cover_image_ids)
    valid_cover_ids, invalid_cover_ids = _validate_cover_ids_for_ops(session, cover_ids=normalized_ids)
    return _create_ocr_batch(
        session,
        actor_user_id=actor_user_id,
        cover_ids=valid_cover_ids,
        invalid_cover_ids=invalid_cover_ids,
        duplicate_cover_ids=duplicate_cover_ids,
        batch_options_json=payload.batch_options_json,
    )


def list_ocr_batches_for_owner(session: Session, *, current_user: User, limit: int = 25) -> list[OcrBatchRead]:
    rows = session.exec(_list_batches_stmt(created_by=current_user.id, limit=limit)).all()
    return [ocr_batch_entity_to_read(session, _sync_batch_runtime_state(session, row)) for row in rows]


def list_ocr_batches_for_ops(session: Session, *, limit: int = 25) -> list[OcrBatchRead]:
    rows = session.exec(_list_batches_stmt(created_by=None, limit=limit)).all()
    return [ocr_batch_entity_to_read(session, _sync_batch_runtime_state(session, row)) for row in rows]


def get_ocr_batch_detail_for_owner(session: Session, *, current_user: User, batch_id: int) -> OcrBatchRead:
    batch = get_ocr_batch_for_owner_or_404(session, current_user=current_user, batch_id=batch_id)
    return ocr_batch_entity_to_read(session, _sync_batch_runtime_state(session, batch))


def get_ocr_batch_detail_for_ops(session: Session, *, batch_id: int) -> OcrBatchRead:
    batch = get_ocr_batch_for_ops_or_404(session, batch_id=batch_id)
    return ocr_batch_entity_to_read(session, _sync_batch_runtime_state(session, batch))


def _enqueue_batch_item(
    session: Session,
    *,
    item: OcrBatchItem,
    actor_user_id: int | None,
) -> None:
    settings = get_settings()
    max_attempts = int(settings.cover_ocr_batch_item_max_enqueue_attempts)
    if item.attempt_count >= max_attempts:
        err = dumps_structured_error(
            error_code=ERROR_CODE_retry_exhausted,
            error_type="retry_exhausted",
            safe_message=f"OCR batch item enqueue attempts exhausted (max={max_attempts}).",
            retryable=False,
            details={"attempt_count": item.attempt_count, "max_enqueue_attempts": max_attempts},
        )
        batch = session.get(OcrBatch, item.batch_id) if item.batch_id is not None else None
        record_ops_event(
            event_type="retry_exhausted",
            status="terminal",
            user_id=actor_user_id,
            message="OCR batch item retry exhausted",
            details={
                "batch_id": item.batch_id,
                "cover_image_id": item.cover_image_id,
                "attempt_count": item.attempt_count,
            },
        )
        _set_item_status(
            session,
            item=item,
            status_value="failed",
            error_message=err,
            actor_user_id=actor_user_id,
        )
        if batch is not None:
            _refresh_batch_summary(session, batch, actor_user_id=actor_user_id)
        return

    if item.status not in {"pending", "failed"}:
        return
    cover = session.get(CoverImage, item.cover_image_id)
    if cover is None:
        _set_item_status(
            session,
            item=item,
            status_value="skipped",
            error_message="Cover image no longer exists",
            actor_user_id=actor_user_id,
        )
        return
    job_id = COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=item.cover_image_id)
    existing_job = fetch_job_by_id(job_id)
    if existing_job is not None and existing_job.get_status(refresh=True) in ACTIVE_RQ_STATUSES:
        item.attempt_count += 1
        item.job_id = existing_job.id
        item.updated_at = _now()
        session.add(item)
        session.flush()
        _set_item_status(
            session,
            item=item,
            status_value="queued",
            job_id=existing_job.id,
            actor_user_id=actor_user_id,
        )
        return

    pending_result = create_pending_cover_image_ocr_result(session, cover_image_id=item.cover_image_id)
    job = enqueue_cover_image_ocr_job(
        cover_image_id=item.cover_image_id,
        user_id=actor_user_id or 0,
        ocr_result_id=pending_result.id,
    )
    item.attempt_count += 1
    item.job_id = job.id
    item.updated_at = _now()
    session.add(item)
    session.flush()
    _set_item_status(
        session,
        item=item,
        status_value="queued",
        job_id=job.id,
        actor_user_id=actor_user_id,
    )


def _enqueue_batch(session: Session, *, batch: OcrBatch, actor_user_id: int | None) -> OcrBatchRead:
    if batch.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled OCR batches cannot be enqueued")
    items = session.exec(
        select(OcrBatchItem)
        .where(OcrBatchItem.batch_id == batch.id)
        .order_by(OcrBatchItem.cover_image_id.asc(), OcrBatchItem.id.asc())
    ).all()
    for item in items:
        if item.status == "pending":
            _enqueue_batch_item(session, item=item, actor_user_id=actor_user_id)
    _refresh_batch_summary(session, batch, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(batch)
    return ocr_batch_entity_to_read(session, batch)


def enqueue_ocr_batch_for_owner(session: Session, *, current_user: User, batch_id: int) -> OcrBatchRead:
    batch = get_ocr_batch_for_owner_or_404(session, current_user=current_user, batch_id=batch_id)
    return _enqueue_batch(session, batch=batch, actor_user_id=current_user.id)


def enqueue_ocr_batch_for_ops(session: Session, *, batch_id: int, actor_user_id: int | None) -> OcrBatchRead:
    batch = get_ocr_batch_for_ops_or_404(session, batch_id=batch_id)
    return _enqueue_batch(session, batch=batch, actor_user_id=actor_user_id)


def _retry_failed_items(session: Session, *, batch: OcrBatch, actor_user_id: int | None) -> OcrBatchRead:
    if batch.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled OCR batches cannot be retried")
    if batch.id is None:
        raise HTTPException(status_code=404, detail="OCR batch not found")
    record_metadata_audit(
        session,
        entity_type="ocr_batch",
        entity_id=batch.id,
        action="ocr_batch_retry_requested",
        before_snapshot=_ocr_batch_snapshot_public(batch),
        after_snapshot=_ocr_batch_snapshot_public(batch),
        actor_user_id=actor_user_id,
    )
    items = session.exec(
        select(OcrBatchItem)
        .where(OcrBatchItem.batch_id == batch.id, OcrBatchItem.status == "failed")
        .order_by(OcrBatchItem.cover_image_id.asc(), OcrBatchItem.id.asc())
    ).all()
    for item in items:
        item.attempt_count = 0
        session.add(item)
    session.flush()
    for item in items:
        _enqueue_batch_item(session, item=item, actor_user_id=actor_user_id)
    _refresh_batch_summary(session, batch, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(batch)
    return ocr_batch_entity_to_read(session, batch)


def retry_failed_ocr_batch_items_for_owner(
    session: Session,
    *,
    current_user: User,
    batch_id: int,
) -> OcrBatchRead:
    batch = get_ocr_batch_for_owner_or_404(session, current_user=current_user, batch_id=batch_id)
    return _retry_failed_items(session, batch=batch, actor_user_id=current_user.id)


def retry_failed_ocr_batch_items_for_ops(
    session: Session,
    *,
    batch_id: int,
    actor_user_id: int | None,
) -> OcrBatchRead:
    batch = get_ocr_batch_for_ops_or_404(session, batch_id=batch_id)
    return _retry_failed_items(session, batch=batch, actor_user_id=actor_user_id)


def _cancel_batch(session: Session, *, batch: OcrBatch, actor_user_id: int | None) -> OcrBatchRead:
    items = session.exec(
        select(OcrBatchItem).where(OcrBatchItem.batch_id == batch.id).order_by(OcrBatchItem.id.asc())
    ).all()
    for item in items:
        if item.status in {"pending", "queued"}:
            _set_item_status(
                session,
                item=item,
                status_value="cancelled",
                actor_user_id=actor_user_id,
            )
    batch.status = "cancelled"
    batch.updated_at = _now()
    batch.completed_at = batch.completed_at or _now()
    session.add(batch)
    _refresh_batch_summary(session, batch, actor_user_id=actor_user_id)
    session.commit()
    session.refresh(batch)
    return ocr_batch_entity_to_read(session, batch)


def cancel_ocr_batch_for_owner(session: Session, *, current_user: User, batch_id: int) -> OcrBatchRead:
    batch = get_ocr_batch_for_owner_or_404(session, current_user=current_user, batch_id=batch_id)
    return _cancel_batch(session, batch=batch, actor_user_id=current_user.id)


def cancel_ocr_batch_for_ops(session: Session, *, batch_id: int, actor_user_id: int | None) -> OcrBatchRead:
    batch = get_ocr_batch_for_ops_or_404(session, batch_id=batch_id)
    return _cancel_batch(session, batch=batch, actor_user_id=actor_user_id)


def _matching_batch_items(
    session: Session,
    *,
    cover_image_id: int,
    job_id: str | None,
    statuses: tuple[str, ...],
) -> list[OcrBatchItem]:
    stmt = select(OcrBatchItem).where(
        OcrBatchItem.cover_image_id == cover_image_id,
        OcrBatchItem.status.in_(statuses),
    )
    rows = session.exec(stmt.order_by(OcrBatchItem.id.asc())).all()
    if job_id is None:
        return rows
    matched = [row for row in rows if row.job_id in {None, job_id} or row.job_id == job_id]
    return matched or rows


def mark_ocr_batch_items_running(session: Session, *, cover_image_id: int, job_id: str | None) -> None:
    affected_batches: set[int] = set()
    for item in _matching_batch_items(session, cover_image_id=cover_image_id, job_id=job_id, statuses=("queued", "pending")):
        item.status = "running"
        item.job_id = job_id or item.job_id
        item.started_at = item.started_at or _now()
        item.updated_at = _now()
        session.add(item)
        affected_batches.add(item.batch_id)
    for batch_id in affected_batches:
        batch = session.get(OcrBatch, batch_id)
        if batch is not None:
            _refresh_batch_summary(session, batch)
    if affected_batches:
        session.commit()


def mark_ocr_batch_items_completed(session: Session, *, cover_image_id: int, job_id: str | None) -> None:
    affected_batches: set[int] = set()
    for item in _matching_batch_items(session, cover_image_id=cover_image_id, job_id=job_id, statuses=("queued", "running")):
        _set_item_status(session, item=item, status_value="completed", job_id=job_id)
        affected_batches.add(item.batch_id)
    for batch_id in affected_batches:
        batch = session.get(OcrBatch, batch_id)
        if batch is not None:
            _refresh_batch_summary(session, batch)
    if affected_batches:
        session.commit()


def mark_ocr_batch_items_failed(
    session: Session,
    *,
    cover_image_id: int,
    job_id: str | None,
    error_message: str,
) -> None:
    affected_batches: set[int] = set()
    for item in _matching_batch_items(session, cover_image_id=cover_image_id, job_id=job_id, statuses=("queued", "running")):
        _set_item_status(
            session,
            item=item,
            status_value="failed",
            job_id=job_id,
            error_message=error_message,
        )
        affected_batches.add(item.batch_id)
    for batch_id in affected_batches:
        batch = session.get(OcrBatch, batch_id)
        if batch is not None:
            _refresh_batch_summary(session, batch)
    if affected_batches:
        session.commit()
