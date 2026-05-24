"""Operations visibility + safe recovery helpers for OCR pipeline resilience."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import CoverImageOcrResult, OcrBatch, OcrBatchItem, OcrReplayItem, OcrReplayRun
from app.schemas.ocr_pipeline_health import (
    OpsBatchFailureSummary,
    OpsPipelineHealth,
    OpsPipelineStaleRow,
    OpsReplayFailureSummary,
)
from app.services.ops_events import record_ops_event
from app.services.ocr_batches import _refresh_batch_summary, _set_item_status
from app.services.ocr_replays import _recompute_run_summary
from app.services.processing_errors import (
    ERROR_CODE_cover_image_corrupt,
    ERROR_CODE_retry_exhausted,
    ERROR_CODE_tesseract_timeout,
    classify_exception,
    dumps_structured_error,
)
from app.services.ocr_batches import ACTIVE_RQ_STATUSES
from app.tasks.queue import fetch_job_by_id


ERROR_CODE_STALE_OCR_JOB = "stale_ocr_processing_row"
ERROR_CODE_STALE_BATCH_ITEM = "stale_batch_item_recovery"
ERROR_CODE_STALE_REPLAY_ITEM = "stale_replay_item_recovery"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _window_start(settings: Settings) -> datetime:
    return _utc_now() - timedelta(hours=max(1, int(settings.ocr_health_window_hours)))


def _json_error_needle(code: str) -> str:
    return f'"error_code":"{code}"'


def count_failed_ocr_in_window(session: Session, cutoff: datetime) -> int:
    stmt = (
        select(func.count())
        .select_from(CoverImageOcrResult)
        .where(
            CoverImageOcrResult.processing_status == "failed",
            CoverImageOcrResult.processed_at.is_not(None),
            CoverImageOcrResult.processed_at >= cutoff,
        )
    )
    return int(session.exec(stmt).one())


def count_failed_ocr_contains(session: Session, cutoff: datetime, needle: str) -> int:
    stmt = (
        select(func.count())
        .select_from(CoverImageOcrResult)
        .where(
            CoverImageOcrResult.processing_status == "failed",
            CoverImageOcrResult.processed_at >= cutoff,
            CoverImageOcrResult.processing_error.contains(needle),
        )
    )
    return int(session.exec(stmt).one())


def count_batch_items_contains(session: Session, cutoff: datetime, needle: str) -> int:
    stmt = (
        select(func.count())
        .select_from(OcrBatchItem)
        .where(
            OcrBatchItem.status == "failed",
            OcrBatchItem.updated_at >= cutoff,
            OcrBatchItem.last_error.contains(needle),
        )
    )
    return int(session.exec(stmt).one())


def count_failed_replay_items_window(session: Session, cutoff: datetime) -> int:
    stmt = (
        select(func.count())
        .select_from(OcrReplayItem)
        .where(OcrReplayItem.status == "failed", OcrReplayItem.updated_at >= cutoff)
    )
    return int(session.exec(stmt).one())


def recent_failed_replay_run_ids(session: Session, cutoff: datetime, *, limit: int = 25) -> list[int]:
    stmt = (
        select(OcrReplayRun.id)
        .where(OcrReplayRun.status == "failed", OcrReplayRun.updated_at >= cutoff)
        .order_by(OcrReplayRun.updated_at.desc(), OcrReplayRun.id.desc())
        .limit(limit)
    )
    return [int(r) for r in session.exec(stmt).all() if r is not None]


def failed_batch_summary(session: Session, cutoff: datetime) -> OpsBatchFailureSummary:
    failed_batch_ids = session.exec(
        select(distinct(OcrBatchItem.batch_id)).where(OcrBatchItem.status == "failed", OcrBatchItem.updated_at >= cutoff)
    ).all()
    batches_n = sum(1 for _ in failed_batch_ids)
    stmt_items = (
        select(func.count())
        .select_from(OcrBatchItem)
        .where(OcrBatchItem.status == "failed", OcrBatchItem.updated_at >= cutoff)
    )
    items_n = int(session.exec(stmt_items).one())
    return OpsBatchFailureSummary(batches_with_failed_items=batches_n, failed_items_total_recent=items_n)


def count_stale_cover_ocr_details(session: Session, stale_cutoff: datetime) -> tuple[int, list[OpsPipelineStaleRow]]:
    stmt = (
        select(CoverImageOcrResult)
        .where(
            CoverImageOcrResult.processing_status == "processing",
            CoverImageOcrResult.processing_started_at.is_not(None),
            CoverImageOcrResult.processing_started_at < stale_cutoff,
        )
        .order_by(CoverImageOcrResult.id.asc())
        .limit(50)
    )
    rows = session.exec(stmt).all()
    stale_rows = [
        OpsPipelineStaleRow(
            category="stale_cover_ocr",
            entity_kind="cover_image_ocr_result",
            entity_id=int(row.id or 0),
            cover_image_id=int(row.cover_image_id),
            detail="processing_status=processing exceeds stale threshold",
            stale_since=(row.processing_started_at.isoformat() if row.processing_started_at else None),
        )
        for row in rows
        if row.id is not None
    ]
    stmt_count = (
        select(func.count())
        .select_from(CoverImageOcrResult)
        .where(
            CoverImageOcrResult.processing_status == "processing",
            CoverImageOcrResult.processing_started_at.is_not(None),
            CoverImageOcrResult.processing_started_at < stale_cutoff,
        )
    )
    return int(session.exec(stmt_count).one()), stale_rows


def stale_batch_panel_rows(session: Session, stale_cutoff: datetime) -> tuple[int, list[OpsPipelineStaleRow]]:
    stmt = (
        select(OcrBatchItem)
        .where(OcrBatchItem.status.in_({"queued", "running"}), OcrBatchItem.updated_at < stale_cutoff)
        .order_by(OcrBatchItem.updated_at.asc(), OcrBatchItem.id.asc())
        .limit(200)
    )
    candidates = session.exec(stmt).all()
    stale_detail: list[OpsPipelineStaleRow] = []

    for item in candidates:
        if item.id is None:
            continue
        if item.job_id:
            job = fetch_job_by_id(item.job_id)
            status = job.get_status(refresh=True) if job is not None else None
            active = status in ACTIVE_RQ_STATUSES if status is not None else False
            if active:
                continue
        stale_detail.append(
            OpsPipelineStaleRow(
                category="stale_batch_item",
                entity_kind="ocr_batch_item",
                entity_id=int(item.id),
                cover_image_id=int(item.cover_image_id),
                detail=f"Queued/running without active worker state (job_id={item.job_id})",
                stale_since=item.updated_at.isoformat() if item.updated_at else None,
            )
        )

    return len(stale_detail), stale_detail[:50]


def stale_replay_details(session: Session, stale_cutoff: datetime) -> tuple[int, list[OpsPipelineStaleRow]]:
    stmt = (
        select(OcrReplayItem, OcrReplayRun)
        .join(OcrReplayRun, OcrReplayItem.replay_run_id == OcrReplayRun.id)
        .where(
            OcrReplayItem.status.in_({"queued", "running"}),
            OcrReplayRun.status == "running",
            OcrReplayItem.updated_at < stale_cutoff,
        )
        .order_by(OcrReplayItem.updated_at.asc(), OcrReplayItem.id.asc())
        .limit(50)
    )
    paired = session.exec(stmt).all()
    details = [
        OpsPipelineStaleRow(
            category="stale_replay_item",
            entity_kind="ocr_replay_item",
            entity_id=int(item.id or 0),
            cover_image_id=int(item.cover_image_id),
            detail=f"replay_run_id={run.id} stalled while run is running",
            stale_since=item.updated_at.isoformat() if item.updated_at else None,
        )
        for item, run in paired
        if item.id is not None
    ]

    stmt_count = (
        select(func.count())
        .select_from(OcrReplayItem)
        .join(OcrReplayRun, OcrReplayItem.replay_run_id == OcrReplayRun.id)
        .where(
            OcrReplayItem.status.in_({"queued", "running"}),
            OcrReplayRun.status == "running",
            OcrReplayItem.updated_at < stale_cutoff,
        )
    )
    return int(session.exec(stmt_count).one()), details


def build_pipeline_health_snapshot(session: Session, settings: Settings) -> OpsPipelineHealth:
    cutoff = _window_start(settings)
    stale_cover_cutoff = _utc_now() - timedelta(seconds=max(60, int(settings.cover_ocr_processing_stale_seconds)))
    stale_batch_cutoff = _utc_now() - timedelta(seconds=max(60, int(settings.ocr_batch_item_orphan_seconds)))
    stale_replay_cutoff = _utc_now() - timedelta(seconds=max(60, int(settings.ocr_replay_item_stuck_seconds)))

    tess_needle = _json_error_needle(ERROR_CODE_tesseract_timeout)
    corrupt_needle = _json_error_needle(ERROR_CODE_cover_image_corrupt)
    exhausted_needle = _json_error_needle(ERROR_CODE_retry_exhausted)

    stale_cover_total, stale_cover_rows = count_stale_cover_ocr_details(session, stale_cover_cutoff)
    stale_batch_total, stale_batch_rows = stale_batch_panel_rows(session, stale_batch_cutoff)
    stale_replay_total, stale_replay_rows_list = stale_replay_details(session, stale_replay_cutoff)

    return OpsPipelineHealth(
        window_hours=int(settings.ocr_health_window_hours),
        cutoff_utc=cutoff,
        failed_ocr_results=count_failed_ocr_in_window(session, cutoff),
        ocr_tesseract_timeouts=count_failed_ocr_contains(session, cutoff, tess_needle),
        corrupt_image_failures=count_failed_ocr_contains(session, cutoff, corrupt_needle),
        retry_exhausted_batch_items=count_batch_items_contains(session, cutoff, exhausted_needle),
        replay_failed_items_total=count_failed_replay_items_window(session, cutoff),
        stale_cover_ocr_processing=stale_cover_total,
        stale_batch_items=stale_batch_total,
        stale_replay_running_items=stale_replay_total,
        stale_batch_rows=stale_batch_rows,
        stale_cover_ocr_rows=stale_cover_rows,
        stale_replay_rows=stale_replay_rows_list,
        replay_failures_recent=OpsReplayFailureSummary(
            failed_items_total_recent=count_failed_replay_items_window(session, cutoff),
            failed_recent_run_ids=recent_failed_replay_run_ids(session, cutoff),
        ),
        batch_failures=failed_batch_summary(session, cutoff),
    )


def recover_stale_ocr_processing_rows(
    session: Session,
    *,
    settings: Settings,
    actor_user_id: int | None,
) -> int:
    cutoff = _utc_now() - timedelta(seconds=max(60, int(settings.cover_ocr_processing_stale_seconds)))
    rows = session.exec(
        select(CoverImageOcrResult)
        .where(
            CoverImageOcrResult.processing_status == "processing",
            CoverImageOcrResult.processing_started_at.is_not(None),
            CoverImageOcrResult.processing_started_at < cutoff,
        )
        .order_by(CoverImageOcrResult.id.asc())
    ).all()
    classifier = classify_exception(ValueError("OCR processing stalled."), stage="cover_ocr_recovery")
    changed = 0
    for row in rows:
        err = dumps_structured_error(
            error_code=ERROR_CODE_STALE_OCR_JOB,
            error_type="stale_job",
            safe_message="OCR processing stalled; recovered for ops visibility.",
            retryable=True,
            details={"classifier": classifier.error_code},
        )
        row.processing_status = "failed"
        row.processing_error = err[:2000]
        row.processing_started_at = None
        row.processed_at = _utc_now()
        session.add(row)
        changed += 1

    if changed > 0:
        session.flush()
        record_ops_event(
            event_type="recovery_action_triggered",
            status="ocr_stale_row_recovery",
            user_id=actor_user_id,
            message=f"Recovered stale OCR rows count={changed}",
            details={"count": changed},
        )
    return changed


def recover_orphan_batch_items(
    session: Session,
    *,
    settings: Settings,
    actor_user_id: int | None,
) -> int:
    cutoff = _utc_now() - timedelta(seconds=max(60, int(settings.ocr_batch_item_orphan_seconds)))

    stmt = (
        select(OcrBatchItem)
        .where(OcrBatchItem.status.in_({"queued", "running"}), OcrBatchItem.updated_at < cutoff)
        .order_by(OcrBatchItem.id.asc())
        .limit(500)
    )
    items = session.exec(stmt).all()
    touched_batches: set[int] = set()
    changed = 0

    for item in items:
        if item.job_id:
            job = fetch_job_by_id(item.job_id)
            status = job.get_status(refresh=True) if job is not None else None
            if status in ACTIVE_RQ_STATUSES:
                continue
            missing_job = job is None
            msg = (
                "Batch item lost worker linkage."
                if not missing_job
                else "Batch item queued without an active Redis job linkage."
            )
        else:
            missing_job = True
            msg = "Batch item missing job id."

        err = dumps_structured_error(
            error_code=ERROR_CODE_STALE_BATCH_ITEM,
            error_type="orphan_detection",
            safe_message=msg,
            retryable=True,
            details={"batch_id": item.batch_id, "job_missing": missing_job},
        )
        touched_batches.add(int(item.batch_id or 0))
        _set_item_status(
            session,
            item=item,
            status_value="failed",
            error_message=err,
            actor_user_id=actor_user_id,
        )
        changed += 1

    touched_batches.discard(0)
    session.flush()

    if touched_batches:
        for batch_id in touched_batches:
            batch = session.get(OcrBatch, batch_id)
            if batch is not None:
                _refresh_batch_summary(session, batch, actor_user_id=actor_user_id)

    if changed > 0:
        record_ops_event(
            event_type="recovery_action_triggered",
            status="batch_item_orphan_recovery",
            user_id=actor_user_id,
            message=f"Recovered stuck OCR batch items count={changed}",
            details={"count": changed},
        )
    return changed


def recover_stale_replay_items(
    session: Session,
    *,
    settings: Settings,
    actor_user_id: int | None,
) -> int:
    cutoff = _utc_now() - timedelta(seconds=max(60, int(settings.ocr_replay_item_stuck_seconds)))

    stmt = (
        select(OcrReplayItem)
        .join(OcrReplayRun, OcrReplayItem.replay_run_id == OcrReplayRun.id)
        .where(
            OcrReplayItem.status.in_({"queued", "running"}),
            OcrReplayRun.status == "running",
            OcrReplayItem.updated_at < cutoff,
        )
        .order_by(OcrReplayItem.id.asc())
    )
    rows = session.exec(stmt).all()
    run_ids: set[int] = set()
    changed = 0
    now = _utc_now()
    for item in rows:
        err = dumps_structured_error(
            error_code=ERROR_CODE_STALE_REPLAY_ITEM,
            error_type="stale_job",
            safe_message="Replay item stalled mid-run.",
            retryable=False,
            details={"replay_run_id": item.replay_run_id},
        )
        item.status = "failed"
        item.last_error = err[:2000]
        item.completed_at = now
        item.updated_at = now
        session.add(item)
        if item.replay_run_id:
            run_ids.add(int(item.replay_run_id))
        changed += 1

    if run_ids:
        session.flush()
        for run_id in run_ids:
            run = session.get(OcrReplayRun, run_id)
            if run is None:
                continue
            refreshed = session.exec(
                select(OcrReplayItem).where(OcrReplayItem.replay_run_id == run_id).order_by(OcrReplayItem.id.asc())
            ).all()
            _recompute_run_summary(run, refreshed)
            session.add(run)

    if changed > 0:
        record_ops_event(
            event_type="recovery_action_triggered",
            status="ocr_replay_stale_recovery",
            user_id=actor_user_id,
            message=f"Recovered stale OCR replay items count={changed}",
            details={"count": changed},
        )
    return changed


def recover_ocr_pipeline(
    session: Session,
    *,
    settings: Settings,
    actor_user_id: int | None,
) -> dict[str, int]:
    a = recover_stale_ocr_processing_rows(session, settings=settings, actor_user_id=actor_user_id)
    b = recover_orphan_batch_items(session, settings=settings, actor_user_id=actor_user_id)
    c = recover_stale_replay_items(session, settings=settings, actor_user_id=actor_user_id)
    session.commit()
    return {"ocr_results_recovered": a, "batch_items_recovered": b, "replay_items_recovered": c}
