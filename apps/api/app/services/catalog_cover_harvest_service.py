from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.models.catalog_master import CatalogImage, CatalogImageFingerprint, CatalogIssue, CatalogSeries, utc_now
from app.services.catalog_import_job_service import (
    complete_job,
    record_failed,
    record_skipped,
    record_updated,
    resume_latest_job,
    start_job,
    update_cursor,
)
from app.services.cover_images import sha256_raw_bytes

LOGGER = logging.getLogger(__name__)

DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0


def _cover_root() -> Path:
    settings = get_settings()
    root = settings.catalog_cover_storage_root.strip() or f"{settings.catalog_storage_root.strip()}/covers"
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _target_path(image: CatalogImage, session: Session) -> Path:
    issue = session.get(CatalogIssue, image.issue_id) if image.issue_id else None
    series = session.get(CatalogSeries, issue.series_id) if issue else None
    pub_part = str(series.publisher_id if series else "unknown")
    series_part = str(series.id if series else "unknown")
    issue_part = str(issue.id if issue else "unknown")
    return _cover_root() / pub_part / series_part / issue_part / f"{image.id}.bin"


def _http_timeout(seconds: float) -> httpx.Timeout:
    return httpx.Timeout(seconds, connect=min(10.0, seconds), read=seconds, write=min(10.0, seconds))


def resolve_catalog_image_local_path(session: Session, image: CatalogImage) -> Path | None:
    if not image.local_path:
        candidates: list[Path] = []
    else:
        stored = Path(image.local_path)
        candidates = [stored]
        if not stored.is_absolute():
            candidates.append(Path.cwd() / stored)
    canonical = _target_path(image, session)
    if canonical not in candidates:
        candidates.append(canonical)
    for path in candidates:
        if path.exists():
            return path
    return None


def _local_cover_file_exists(session: Session, image: CatalogImage) -> bool:
    return resolve_catalog_image_local_path(session, image) is not None


def _ready_images_missing_fingerprint(
    session: Session,
    *,
    after_image_id: int,
    source: str | None,
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
    )
    if source:
        statement = statement.where(CatalogImage.source == source)
    candidates = session.exec(statement.limit(max(limit * 5, limit))).all()
    rows: list[CatalogImage] = []
    for row in candidates:
        if len(rows) >= limit:
            break
        if not _local_cover_file_exists(session, row):
            rows.append(row)
    return rows


def _ready_images_missing_local_file(
    session: Session,
    *,
    after_image_id: int,
    source: str | None,
    limit: int,
) -> list[CatalogImage]:
    statement = (
        select(CatalogImage)
        .where(CatalogImage.download_status == "ready")
        .where(CatalogImage.id > after_image_id)
        .order_by(CatalogImage.id)
    )
    if source:
        statement = statement.where(CatalogImage.source == source)
    rows: list[CatalogImage] = []
    chunk_start = after_image_id
    chunk_size = max(limit * 50, 500)
    while len(rows) < limit:
        chunk = session.exec(
            statement.where(CatalogImage.id > chunk_start).limit(chunk_size)
        ).all()
        if not chunk:
            break
        for row in chunk:
            chunk_start = int(row.id or 0)
            if not _local_cover_file_exists(session, row):
                rows.append(row)
                if len(rows) >= limit:
                    break
        if len(chunk) < chunk_size:
            break
    return rows


def harvest_image(
    session: Session,
    image: CatalogImage,
    *,
    dry_run: bool = False,
    user_agent: str | None = None,
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> CatalogImage:
    if _local_cover_file_exists(session, image) and image.download_status == "ready":
        return image
    if not image.source_url:
        image.download_status = "missing_source"
        image.download_error = "no source_url"
        image.updated_at = utc_now()
        session.add(image)
        return image
    if dry_run:
        return image
    target = _target_path(image, session)
    try:
        headers = {"User-Agent": user_agent or get_settings().catalog_import_user_agent}
        response = httpx.get(
            image.source_url,
            timeout=_http_timeout(http_timeout_seconds),
            follow_redirects=True,
            headers=headers,
        )
        response.raise_for_status()
        body = response.content
        if not body:
            raise RuntimeError("empty response body")
        checksum = sha256_raw_bytes(body)
        dup = session.exec(
            select(CatalogImage).where(CatalogImage.checksum == checksum).where(CatalogImage.id != image.id)
        ).first()
        if dup and dup.local_path:
            image.local_path = dup.local_path
            image.checksum = checksum
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            image.local_path = str(target)
            image.checksum = checksum
        image.file_size_bytes = len(body)
        image.content_type = response.headers.get("content-type")
        image.download_status = "ready"
        image.download_error = None
        image.downloaded_at = utc_now()
    except Exception as exc:
        image.download_status = "failed"
        image.download_error = str(exc)[:2000]
    image.updated_at = utc_now()
    session.add(image)
    return image


def _flush_batch(session: Session, *, dry_run: bool) -> None:
    if not dry_run:
        session.commit()


def run_cover_harvest(
    session: Session,
    *,
    source: str | None = None,
    missing_only: bool = True,
    failed_only: bool = False,
    repair_missing_files: bool = False,
    repair_missing_fingerprints_only: bool = False,
    limit: int = 100,
    dry_run: bool = False,
    sleep_seconds: float | None = None,
    resume: bool = False,
    batch_size: int = 1,
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> dict:
    settings = get_settings()
    sleep = sleep_seconds if sleep_seconds is not None else settings.catalog_import_sleep_seconds
    commit_every = max(1, int(batch_size))
    job_source = source or "ALL"

    if repair_missing_files:
        job_type = "cover_repair_fingerprint" if repair_missing_fingerprints_only else "cover_repair"
    else:
        job_type = "cover_harvest"

    job = resume_latest_job(session, source=job_source, job_type=job_type) if resume else None
    if job is None or job.status == "completed":
        job = start_job(session, source=job_source, job_type=job_type, dry_run=dry_run, cursor={"last_image_id": 0})
        _flush_batch(session, dry_run=dry_run)
    elif resume and job.status == "running":
        LOGGER.info("Resuming cover harvest job_id=%s cursor=%s", job.id, job.cursor)

    last_image_id = int((job.cursor or {}).get("last_image_id", 0))

    statement = select(CatalogImage).where(CatalogImage.id > last_image_id).order_by(CatalogImage.id)
    if source:
        statement = statement.where(CatalogImage.source == source)
    if repair_missing_files:
        if repair_missing_fingerprints_only:
            rows = _ready_images_missing_fingerprint(
                session,
                after_image_id=last_image_id,
                source=source,
                limit=limit,
            )
        else:
            rows = _ready_images_missing_local_file(
                session,
                after_image_id=last_image_id,
                source=source,
                limit=limit,
            )
    else:
        if missing_only and not failed_only:
            statement = statement.where(CatalogImage.download_status == "pending")
        if failed_only:
            statement = statement.where(CatalogImage.download_status == "failed")
        rows = list(session.exec(statement.limit(limit)).all())
    LOGGER.info(
        "cover_harvest starting job_id=%s batch=%s after_image_id=%s selected=%s",
        job.id,
        commit_every,
        last_image_id,
        len(rows),
    )

    for idx, row in enumerate(rows):
        image_id = int(row.id or 0)
        before_status = row.download_status
        repair_before = repair_missing_files and not _local_cover_file_exists(session, row)
        try:
            harvest_image(
                session,
                row,
                dry_run=dry_run,
                user_agent=settings.catalog_import_user_agent,
                http_timeout_seconds=http_timeout_seconds,
            )
            if row.download_status == "ready" and before_status == "ready":
                if repair_before and _local_cover_file_exists(session, row):
                    record_updated(session, job)
                else:
                    record_skipped(session, job)
            elif row.download_status == "failed":
                record_failed(
                    session,
                    job,
                    source=row.source,
                    external_id=str(image_id),
                    record_type="catalog_image",
                    error_type="download",
                    error_message=row.download_error or "download failed",
                )
            elif row.download_status == "missing_source":
                record_failed(
                    session,
                    job,
                    source=row.source,
                    external_id=str(image_id),
                    record_type="catalog_image",
                    error_type="missing_source",
                    error_message=row.download_error or "missing source_url",
                )
            else:
                record_updated(session, job)
        except Exception as exc:
            record_failed(
                session,
                job,
                source=row.source,
                external_id=str(image_id),
                record_type="catalog_image",
                error_type="download",
                error_message=str(exc),
            )
            row.download_status = "failed"
            row.download_error = str(exc)[:2000]
            row.updated_at = utc_now()
            session.add(row)

        update_cursor(session, job, {"last_image_id": image_id})
        if (idx + 1) % commit_every == 0:
            _flush_batch(session, dry_run=dry_run)
            LOGGER.info(
                "cover_harvest progress %s/%s image_id=%s status=%s job_updated=%s job_failed=%s",
                idx + 1,
                len(rows),
                image_id,
                row.download_status,
                job.total_updated,
                job.total_failed,
            )
        if sleep > 0:
            time.sleep(sleep)

    _flush_batch(session, dry_run=dry_run)
    summary = complete_job(session, job)
    _flush_batch(session, dry_run=dry_run)
    LOGGER.info(
        "cover_harvest complete job_id=%s updated=%s skipped=%s failed=%s",
        summary.job_id,
        summary.total_updated,
        summary.total_skipped,
        summary.total_failed,
    )
    return summary.__dict__
