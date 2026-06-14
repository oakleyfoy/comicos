from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint
from app.services.catalog_bulk_enrichment_selection import (
    count_missing_fingerprints,
    count_ready_covers,
    count_valid_fingerprints_on_ready_covers,
    select_ready_covers_needing_fingerprint,
)
from app.services.catalog_fingerprint_service import fingerprint_catalog_image
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


def fingerprint_coverage(session: Session) -> dict:
    total = count_ready_covers(session)
    if total == 0:
        return {"downloaded_covers": 0, "fingerprint_count": 0, "coverage_pct": 0.0}
    covered = count_valid_fingerprints_on_ready_covers(session)
    return {
        "downloaded_covers": total,
        "fingerprint_count": covered,
        "coverage_pct": round(100.0 * covered / total, 2),
    }


def _flush(session: Session, *, dry_run: bool) -> None:
    if not dry_run:
        session.commit()


def count_fingerprint_remaining(session: Session) -> int:
    return count_missing_fingerprints(session)


def run_bulk_fingerprints(
    session: Session,
    *,
    missing_only: bool = True,
    limit: int = 200,
    dry_run: bool = False,
    resume: bool = False,
    batch_size: int = 25,
) -> dict:
    commit_every = max(1, int(batch_size))
    job = resume_latest_job(session, source="INTERNAL", job_type="fingerprint_batch") if resume else None
    last_image_id = int((job.cursor or {}).get("last_image_id", 0)) if job else 0
    if job is None or job.status == "completed":
        job = start_job(
            session,
            source="INTERNAL",
            job_type="fingerprint_batch",
            dry_run=dry_run,
            cursor={"last_image_id": 0 if missing_only else last_image_id},
        )
        if missing_only:
            last_image_id = 0
        _flush(session, dry_run=dry_run)
    elif resume and job.status == "running":
        LOGGER.info("Resuming fingerprint job_id=%s cursor=%s", job.id, job.cursor)
        if missing_only:
            last_image_id = 0

    ready_covers_available = count_ready_covers(session)
    missing_fingerprints_available = count_missing_fingerprints(session)

    selection_after_id = None if missing_only else last_image_id
    if missing_only:
        rows = select_ready_covers_needing_fingerprint(session, limit=limit)
    else:
        rows = select_ready_covers_needing_fingerprint(session, limit=limit, after_image_id=selection_after_id)
        if not rows:
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

    selected_for_fingerprint_batch = len(rows)
    LOGGER.info(
        "ready_covers_available=%s missing_fingerprints_available=%s selected_for_fingerprint_batch=%s",
        ready_covers_available,
        missing_fingerprints_available,
        selected_for_fingerprint_batch,
    )

    fp_by_image = {int(r.image_id): r for r in session.exec(select(CatalogImageFingerprint)).all()}
    processed = 0
    for idx, image in enumerate(rows):
        iid = int(image.id or 0)
        try:
            row = fingerprint_catalog_image(session, iid, dry_run=dry_run)
            if row is None or not (row.phash or row.dhash or row.ahash):
                record_skipped(session, job)
            else:
                record_updated(session, job)
                processed += 1
                fp_by_image[iid] = row
        except Exception as exc:
            record_failed(
                session,
                job,
                source="INTERNAL",
                external_id=str(iid),
                record_type="fingerprint",
                error_type="processing",
                error_message=str(exc),
            )
        update_cursor(session, job, {"last_image_id": iid})
        if (idx + 1) % commit_every == 0:
            _flush(session, dry_run=dry_run)
            LOGGER.info("fingerprint progress processed=%s limit=%s image_id=%s", processed, limit, iid)

    _flush(session, dry_run=dry_run)
    summary = complete_job(session, job)
    _flush(session, dry_run=dry_run)
    LOGGER.info("fingerprint batch complete updated=%s failed=%s", summary.total_updated, summary.total_failed)
    return {**summary.__dict__, **fingerprint_coverage(session)}
