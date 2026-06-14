from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogOcrMetadata
from app.services.catalog_bulk_enrichment_selection import (
    count_missing_ocr,
    count_ocr_rows_on_ready_covers,
    count_ready_covers,
    select_ready_covers_needing_ocr,
)
from app.services.catalog_cover_ocr_service import (
    MISSING_LOCAL_IMAGE,
    OCR_EXCEPTION,
    classify_ocr_skip_bucket,
    extract_ocr_from_image_path_result,
    log_ocr_skip,
    store_ocr_for_image,
    tesseract_runtime_diagnostics,
)
from app.services.catalog_cover_harvest_service import resolve_catalog_image_local_path
from app.services.catalog_import_job_service import (
    complete_job,
    record_failed,
    record_skipped,
    record_updated,
    resume_latest_job,
    start_job,
    update_cursor,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class OcrSkipBreakdown:
    skipped_existing_ocr: int = 0
    skipped_missing_file: int = 0
    skipped_missing_tesseract: int = 0
    skipped_image_load_error: int = 0
    skipped_empty_text: int = 0
    skipped_other: int = 0

    def record(self, bucket: str) -> None:
        if bucket == "skipped_existing_ocr":
            self.skipped_existing_ocr += 1
        elif bucket == "skipped_missing_file":
            self.skipped_missing_file += 1
        elif bucket == "skipped_missing_tesseract":
            self.skipped_missing_tesseract += 1
        elif bucket == "skipped_image_load_error":
            self.skipped_image_load_error += 1
        elif bucket == "skipped_empty_text":
            self.skipped_empty_text += 1
        else:
            self.skipped_other += 1

    def as_dict(self) -> dict[str, int]:
        return {
            "skipped_existing_ocr": self.skipped_existing_ocr,
            "skipped_missing_file": self.skipped_missing_file,
            "skipped_missing_tesseract": self.skipped_missing_tesseract,
            "skipped_image_load_error": self.skipped_image_load_error,
            "skipped_empty_text": self.skipped_empty_text,
            "skipped_other": self.skipped_other,
        }


def _count_existing_ocr_rows(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(CatalogOcrMetadata)).one())


def ocr_coverage(session: Session) -> dict:
    total = count_ready_covers(session)
    if total == 0:
        return {"downloaded_covers": 0, "ocr_count": 0, "coverage_pct": 0.0}
    with_ocr = count_ocr_rows_on_ready_covers(session)
    return {"downloaded_covers": total, "ocr_count": with_ocr, "coverage_pct": round(100.0 * with_ocr / total, 2)}


def _flush(session: Session, *, dry_run: bool) -> None:
    if not dry_run:
        session.commit()


def count_ocr_remaining(session: Session) -> int:
    return count_missing_ocr(session)


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
            cursor={"last_image_id": 0 if missing_only else last_image_id},
        )
        if missing_only:
            last_image_id = 0
        _flush(session, dry_run=dry_run)
    elif resume and job.status == "running":
        LOGGER.info("Resuming OCR job_id=%s cursor=%s", job.id, job.cursor)
        if missing_only:
            last_image_id = 0

    tess_diag = tesseract_runtime_diagnostics()
    LOGGER.info("ocr_tesseract_runtime=%s", tess_diag)

    ready_covers_available = count_ready_covers(session)
    missing_ocr_available = count_missing_ocr(session)
    existing_ocr_rows = _count_existing_ocr_rows(session)

    if missing_only:
        rows = select_ready_covers_needing_ocr(session, limit=limit)
    else:
        rows = list(
            session.exec(
                select(CatalogImage)
                .where(CatalogImage.download_status == "ready")
                .where(CatalogImage.image_type == "cover")
                .where(CatalogImage.id > last_image_id)
                .order_by(CatalogImage.id)
                .limit(limit)
            ).all()
        )

    selected_for_ocr_batch = len(rows)
    skip_breakdown = OcrSkipBreakdown()
    processed = 0

    LOGGER.info(
        "ready_covers_available=%s existing_ocr_rows=%s missing_ocr_rows=%s selected_for_ocr_batch=%s",
        ready_covers_available,
        existing_ocr_rows,
        missing_ocr_available,
        selected_for_ocr_batch,
    )

    existing_ids = {int(r.image_id) for r in session.exec(select(CatalogOcrMetadata)).all() if r.image_id}

    for idx, image in enumerate(rows):
        iid = int(image.id or 0)
        if missing_only and iid in existing_ids:
            skip_breakdown.record("skipped_existing_ocr")
            record_skipped(session, job)
            update_cursor(session, job, {"last_image_id": iid})
            log_ocr_skip(image_id=iid, reason="EXISTING_OCR_METADATA", detail="catalog_ocr_metadata row present")
            continue

        local_path = resolve_catalog_image_local_path(session, image)
        if local_path is None:
            skip_breakdown.record("skipped_missing_file")
            log_ocr_skip(image_id=iid, reason=MISSING_LOCAL_IMAGE, detail="catalog_image local file not found")
            record_skipped(session, job)
            update_cursor(session, job, {"last_image_id": iid})
            continue

        try:
            result = extract_ocr_from_image_path_result(str(local_path))
            if result.skip_reason:
                bucket = classify_ocr_skip_bucket(result.skip_reason)
                if result.skip_reason == OCR_EXCEPTION:
                    skip_breakdown.record("skipped_image_load_error")
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
                    skip_breakdown.record(bucket)
                    record_skipped(session, job)
                log_ocr_skip(image_id=iid, reason=result.skip_reason, detail=result.detail)
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
                existing_ids.add(iid)
        except Exception as exc:
            skip_breakdown.record("skipped_image_load_error")
            log_ocr_skip(image_id=iid, reason=OCR_EXCEPTION, detail=str(exc)[:500])
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

    breakdown = skip_breakdown.as_dict()
    LOGGER.info(
        "ocr batch complete updated=%s failed=%s skip_reason_breakdown=%s tesseract_available=%s",
        summary.total_updated,
        summary.total_failed,
        breakdown,
        tess_diag.get("tesseract_available"),
    )
    return {
        **summary.__dict__,
        **ocr_coverage(session),
        "selected_for_ocr_batch": selected_for_ocr_batch,
        "existing_ocr_rows": existing_ocr_rows,
        "missing_ocr_rows": missing_ocr_available,
        "skip_reason_breakdown": breakdown,
        "tesseract_runtime": tess_diag,
        "ocr_rows_created_this_batch": processed,
    }
