from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogOcrMetadata
from app.services.catalog_cover_ocr_service import (
    extract_ocr_from_image_path_result,
    log_ocr_skip,
    store_ocr_for_image,
)
from app.services.catalog_import_job_service import (
    complete_job,
    record_failed,
    record_skipped,
    record_updated,
    resume_latest_job,
    start_job,
    update_cursor,
)
from app.services.catalog_cover_ocr_service import parse_ocr_metadata  # noqa: F401 — re-export for tests

LOGGER = logging.getLogger(__name__)


def ocr_coverage(session: Session) -> dict:
    images = session.exec(select(CatalogImage).where(CatalogImage.download_status == "ready")).all()
    total = len(images)
    if total == 0:
        return {"downloaded_covers": 0, "ocr_count": 0, "coverage_pct": 0.0}
    with_ocr = len(session.exec(select(CatalogOcrMetadata).where(CatalogOcrMetadata.image_id.is_not(None))).all())
    return {"downloaded_covers": total, "ocr_count": with_ocr, "coverage_pct": round(100.0 * with_ocr / total, 2)}


def _flush(session: Session, *, dry_run: bool) -> None:
    if not dry_run:
        session.commit()


def run_bulk_ocr(
    session: Session,
    *,
    missing_only: bool = True,
    limit: int = 100,
    dry_run: bool = False,
    resume: bool = False,
    batch_size: int = 25,
) -> dict:
    commit_every = max(1, int(batch_size))
    job = resume_latest_job(session, source="INTERNAL", job_type="ocr_batch") if resume else None
    last_image_id = int((job.cursor or {}).get("last_image_id", 0)) if job else 0
    if job is None or job.status == "completed":
        job = start_job(
            session,
            source="INTERNAL",
            job_type="ocr_batch",
            dry_run=dry_run,
            cursor={"last_image_id": last_image_id},
        )
        _flush(session, dry_run=dry_run)
    elif resume and job.status == "running":
        LOGGER.info("Resuming OCR job_id=%s cursor=%s", job.id, job.cursor)

    existing = {int(r.image_id) for r in session.exec(select(CatalogOcrMetadata)).all() if r.image_id}
    statement = (
        select(CatalogImage)
        .where(CatalogImage.download_status == "ready")
        .where(CatalogImage.id > last_image_id)
        .order_by(CatalogImage.id)
    )
    rows = session.exec(statement.limit(limit * 2)).all()
    processed = 0
    for idx, image in enumerate(rows):
        if processed >= limit:
            break
        iid = int(image.id or 0)
        if missing_only and iid in existing:
            record_skipped(session, job)
            update_cursor(session, job, {"last_image_id": iid})
            LOGGER.info("ocr skip image_id=%s reason=EXISTING_OCR_METADATA", iid)
            continue
        if not image.local_path:
            log_ocr_skip(image_id=iid, reason="MISSING_LOCAL_IMAGE", detail="catalog_image.local_path is empty")
            record_skipped(session, job)
            update_cursor(session, job, {"last_image_id": iid})
            continue
        try:
            result = extract_ocr_from_image_path_result(image.local_path)
            if result.skip_reason:
                log_ocr_skip(image_id=iid, reason=result.skip_reason, detail=result.detail)
                if result.skip_reason == "OCR_EXCEPTION":
                    record_failed(
                        session,
                        job,
                        source="INTERNAL",
                        external_id=str(iid),
                        record_type="ocr",
                        error_type="processing",
                        error_message=result.detail or result.skip_reason,
                    )
                else:
                    record_skipped(session, job)
                update_cursor(session, job, {"last_image_id": iid})
                continue
            text = result.text or ""
            if dry_run:
                record_updated(session, job)
                processed += 1
            else:
                store_ocr_for_image(
                    session,
                    image_id=iid,
                    issue_id=image.issue_id,
                    variant_id=image.variant_id,
                    ocr_text=text,
                )
                record_updated(session, job)
                processed += 1
                existing.add(iid)
        except Exception as exc:
            log_ocr_skip(image_id=iid, reason="OCR_EXCEPTION", detail=str(exc)[:500])
            record_failed(
                session,
                job,
                source="INTERNAL",
                external_id=str(iid),
                record_type="ocr",
                error_type="processing",
                error_message=str(exc),
            )
        update_cursor(session, job, {"last_image_id": iid})
        if (idx + 1) % commit_every == 0:
            _flush(session, dry_run=dry_run)
            LOGGER.info("ocr progress processed=%s limit=%s image_id=%s", processed, limit, iid)

    _flush(session, dry_run=dry_run)
    summary = complete_job(session, job)
    _flush(session, dry_run=dry_run)
    LOGGER.info("ocr batch complete updated=%s failed=%s", summary.total_updated, summary.total_failed)
    return {**summary.__dict__, **ocr_coverage(session)}
