from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.models.catalog_master import CatalogImage, CatalogImageFingerprint
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
    images = session.exec(select(CatalogImage).where(CatalogImage.download_status == "ready")).all()
    total = len(images)
    if total == 0:
        return {"downloaded_covers": 0, "fingerprint_count": 0, "coverage_pct": 0.0}
    fp_ids = {
        int(r.image_id)
        for r in session.exec(select(CatalogImageFingerprint)).all()
        if r.phash or r.dhash or r.ahash
    }
    covered = sum(1 for img in images if int(img.id or 0) in fp_ids)
    return {
        "downloaded_covers": total,
        "fingerprint_count": covered,
        "coverage_pct": round(100.0 * covered / total, 2),
    }


def _flush(session: Session, *, dry_run: bool) -> None:
    if not dry_run:
        session.commit()


def _ready_images_needing_fingerprint(
    session: Session,
    *,
    after_image_id: int,
    limit: int,
) -> list[CatalogImage]:
    no_hash = or_(
        CatalogImageFingerprint.id.is_(None),
        (col(CatalogImageFingerprint.phash).is_(None))
        & (col(CatalogImageFingerprint.dhash).is_(None))
        & (col(CatalogImageFingerprint.ahash).is_(None)),
    )
    statement = (
        select(CatalogImage)
        .outerjoin(CatalogImageFingerprint, CatalogImageFingerprint.image_id == CatalogImage.id)
        .where(CatalogImage.download_status == "ready")
        .where(CatalogImage.id > after_image_id)
        .where(no_hash)
        .order_by(CatalogImage.id)
        .limit(limit)
    )
    return list(session.exec(statement).all())


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
            cursor={"last_image_id": 0 if missing_only and not resume else last_image_id},
        )
        if missing_only and not resume:
            last_image_id = 0
        _flush(session, dry_run=dry_run)
    elif resume and job.status == "running":
        LOGGER.info("Resuming fingerprint job_id=%s cursor=%s", job.id, job.cursor)

    fp_by_image = {int(r.image_id): r for r in session.exec(select(CatalogImageFingerprint)).all()}
    if missing_only:
        rows = _ready_images_needing_fingerprint(session, after_image_id=last_image_id, limit=limit)
    else:
        rows = list(
            session.exec(
                select(CatalogImage)
                .where(CatalogImage.download_status == "ready")
                .where(CatalogImage.id > last_image_id)
                .order_by(CatalogImage.id)
                .limit(limit)
            ).all()
        )
    processed = 0
    for idx, image in enumerate(rows):
        iid = int(image.id or 0)
        if not image.local_path:
            record_skipped(session, job)
            update_cursor(session, job, {"last_image_id": iid})
            continue
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
