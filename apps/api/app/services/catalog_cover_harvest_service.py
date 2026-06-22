from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from sqlalchemy import func, or_, text
from sqlmodel import Session, col, select

from app.core.config import API_ROOT, get_settings
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


def _resolve_storage_path(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    for base in (Path.cwd(), API_ROOT):
        candidate = base / p
        if candidate.exists():
            return candidate
    return API_ROOT / p


def _cover_root() -> Path:
    settings = get_settings()
    root = settings.catalog_cover_storage_root.strip() or f"{settings.catalog_storage_root.strip()}/covers"
    return _resolve_storage_path(root)


def _target_path(image: CatalogImage, session: Session) -> Path:
    issue = session.get(CatalogIssue, image.issue_id) if image.issue_id else None
    series = session.get(CatalogSeries, issue.series_id) if issue else None
    pub_part = str(series.publisher_id if series else "unknown")
    series_part = str(series.id if series else "unknown")
    issue_part = str(issue.id if issue else "unknown")
    return _cover_root() / pub_part / series_part / issue_part / f"{image.id}.bin"


def _http_timeout(seconds: float) -> httpx.Timeout:
    return httpx.Timeout(seconds, connect=min(10.0, seconds), read=seconds, write=min(10.0, seconds))


def resolve_catalog_image_local_path_fast(image: CatalogImage) -> Path | None:
    """Disk-only path resolution (no DB). Use when local_path is populated after harvest."""
    if not image.local_path:
        return None
    stored = Path(image.local_path)
    candidates: list[Path] = [stored]
    if not stored.is_absolute():
        candidates.append(Path.cwd() / stored)
        candidates.append(API_ROOT / stored)
    for path in candidates:
        try:
            if path.exists():
                return path
        except OSError:
            continue
    return None


def resolve_catalog_image_local_path(session: Session, image: CatalogImage) -> Path | None:
    fast = resolve_catalog_image_local_path_fast(image)
    if fast is not None:
        return fast
    canonical = _target_path(image, session)
    if canonical.exists():
        return canonical
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


# (body, content_type, error) — error is non-None when the fetch failed.
FetchedBytes = tuple[bytes | None, str | None, str | None]


def _fetch_image_bytes(client: httpx.Client, source_url: str) -> FetchedBytes:
    """Pure network fetch with no DB/session access — safe to run in worker threads.

    Uses a shared keep-alive client: every cover is on the same host, so reusing
    pooled TLS connections avoids a per-image handshake (~60x faster in practice).
    """
    try:
        response = client.get(source_url)
        response.raise_for_status()
        body = response.content
        if not body:
            return (None, None, "empty response body")
        return (body, response.headers.get("content-type"), None)
    except Exception as exc:  # noqa: BLE001 - surfaced as a per-image download error
        return (None, None, str(exc)[:2000])


def harvest_image(
    session: Session,
    image: CatalogImage,
    *,
    dry_run: bool = False,
    user_agent: str | None = None,
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    prefetched: FetchedBytes | None = None,
    dedup: bool = True,
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
        if prefetched is not None:
            body, content_type, fetch_error = prefetched
            if fetch_error is not None:
                raise RuntimeError(fetch_error)
            if not body:
                raise RuntimeError("empty response body")
        else:
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
            content_type = response.headers.get("content-type")
        checksum = sha256_raw_bytes(body)
        # The dedup lookup is a per-image remote round-trip; skipping it removes the
        # main-thread bottleneck at the cost of occasionally storing identical bytes twice.
        dup = (
            session.exec(
                select(CatalogImage).where(CatalogImage.checksum == checksum).where(CatalogImage.id != image.id)
            ).first()
            if dedup
            else None
        )
        if dup and dup.local_path:
            image.local_path = dup.local_path
            image.checksum = checksum
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            image.local_path = str(target)
            image.checksum = checksum
        image.file_size_bytes = len(body)
        image.content_type = content_type
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


# Columns written by harvest_image, with the casts needed for an untyped VALUES list.
_IMAGE_UPDATE_COLS = (
    "download_status",
    "local_path",
    "checksum",
    "file_size_bytes",
    "content_type",
    "download_error",
    "downloaded_at",
    "updated_at",
)
_IMAGE_UPDATE_CASTS = {
    "file_size_bytes": "integer",
    "downloaded_at": "timestamptz",
    "updated_at": "timestamptz",
}


def _image_update_row(image: CatalogImage) -> dict:
    row = {"id": int(image.id or 0)}
    for c in _IMAGE_UPDATE_COLS:
        row[c] = getattr(image, c, None)
    return row


def _bulk_apply_image_updates(session: Session, updates: list[dict]) -> None:
    """Apply many catalog_image field updates in ONE round-trip.

    pg8000 has no statement pipelining, so an ORM flush (or executemany) of N dirty
    rows is N sequential round-trips to the remote DB — the harvest's true bottleneck.
    A single UPDATE ... FROM (VALUES ...) writes the whole batch in one statement.
    """
    if not updates:
        return
    rows_sql: list[str] = []
    params: dict = {}
    for k, u in enumerate(updates):
        placeholders = [f":id_{k}"] + [f":{c}_{k}" for c in _IMAGE_UPDATE_COLS]
        rows_sql.append("(" + ",".join(placeholders) + ")")
        params[f"id_{k}"] = u["id"]
        for c in _IMAGE_UPDATE_COLS:
            params[f"{c}_{k}"] = u.get(c)
    set_clause = ", ".join(
        f"{c} = v.{c}::{_IMAGE_UPDATE_CASTS.get(c, 'varchar')}" for c in _IMAGE_UPDATE_COLS
    )
    value_cols = "id, " + ", ".join(_IMAGE_UPDATE_COLS)
    sql = text(
        f"UPDATE catalog_image AS c SET {set_clause} "
        f"FROM (VALUES {', '.join(rows_sql)}) AS v({value_cols}) "
        f"WHERE c.id = v.id::bigint"
    )
    session.connection().execute(sql, params)


def count_cover_harvest_remaining(
    session: Session,
    *,
    source: str | None = None,
    missing_only: bool = True,
    failed_only: bool = False,
    repair_missing_files: bool = False,
    repair_missing_fingerprints_only: bool = False,
) -> int:
    if repair_missing_files:
        if repair_missing_fingerprints_only:
            probe = _ready_images_missing_fingerprint(session, after_image_id=0, source=source, limit=1)
        else:
            probe = _ready_images_missing_local_file(session, after_image_id=0, source=source, limit=1)
        return len(probe)
    statement = select(func.count()).select_from(CatalogImage)
    if source:
        statement = statement.where(CatalogImage.source == source)
    if failed_only:
        statement = statement.where(CatalogImage.download_status == "failed")
    elif missing_only:
        statement = statement.where(CatalogImage.download_status == "pending")
    return int(session.exec(statement).one())


def _make_harvest_client(
    *,
    user_agent: str,
    http_timeout_seconds: float,
    concurrency: int,
) -> httpx.Client:
    workers = max(1, int(concurrency))
    return httpx.Client(
        timeout=_http_timeout(http_timeout_seconds),
        follow_redirects=True,
        headers={"User-Agent": user_agent},
        limits=httpx.Limits(max_connections=workers, max_keepalive_connections=workers),
    )


def _prefetch_window(
    session: Session,
    window: list[CatalogImage],
    *,
    client: httpx.Client,
    concurrency: int,
) -> dict[int, FetchedBytes]:
    """Download bytes for a window of images in parallel.

    Session-touching checks (local-file existence) run here on the main thread;
    only the pure-network fetch is dispatched to worker threads.
    """
    to_fetch: list[tuple[int, str]] = []
    for row in window:
        rid = int(row.id or 0)
        if not row.source_url:
            continue
        if _local_cover_file_exists(session, row) and row.download_status == "ready":
            continue
        to_fetch.append((rid, row.source_url))
    if not to_fetch:
        return {}
    prefetch: dict[int, FetchedBytes] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as executor:
        future_to_id = {
            executor.submit(_fetch_image_bytes, client, url): rid for rid, url in to_fetch
        }
        for future in as_completed(future_to_id):
            rid = future_to_id[future]
            try:
                prefetch[rid] = future.result()
            except Exception as exc:  # noqa: BLE001 - recorded as a per-image error downstream
                prefetch[rid] = (None, None, str(exc)[:2000])
    return prefetch


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
    concurrency: int = 1,
    dedup: bool = True,
) -> dict:
    settings = get_settings()
    sleep = sleep_seconds if sleep_seconds is not None else settings.catalog_import_sleep_seconds
    commit_every = max(1, int(batch_size))
    concurrency = max(1, int(concurrency))
    # Bound in-flight bytes in RAM: prefetch a sliding window, not the whole batch.
    download_window = concurrency * 4 if concurrency > 1 else 0
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

    # Warm the identity map for issue->series path resolution in 2 bulk queries
    # instead of ~2 per-image round-trips to the remote DB (the real bottleneck).
    # NOTE: the identity map holds WEAK references, so we must keep strong refs to
    # the warmed rows for the whole batch or session.get() silently re-queries.
    _warm_issues: list[CatalogIssue] = []
    _warm_series: list[CatalogSeries] = []
    issue_ids = {int(r.issue_id) for r in rows if r.issue_id}
    if issue_ids:
        _warm_issues = list(session.exec(select(CatalogIssue).where(col(CatalogIssue.id).in_(issue_ids))).all())
        series_ids = {int(i.series_id) for i in _warm_issues if i.series_id}
        if series_ids:
            _warm_series = list(
                session.exec(select(CatalogSeries).where(col(CatalogSeries.id).in_(series_ids))).all()
            )

    LOGGER.info(
        "cover_harvest starting job_id=%s batch=%s after_image_id=%s selected=%s",
        job.id,
        commit_every,
        last_image_id,
        len(rows),
    )

    harvest_client = (
        _make_harvest_client(
            user_agent=settings.catalog_import_user_agent,
            http_timeout_seconds=http_timeout_seconds,
            concurrency=concurrency,
        )
        if download_window and not dry_run
        else None
    )
    # On Postgres, batch the per-image row writes into a single VALUES UPDATE per
    # commit (one round-trip) instead of N ORM UPDATEs. Other dialects fall back to
    # the normal ORM flush.
    use_bulk = (not dry_run) and session.connection().dialect.name == "postgresql"
    pending_updates: list[dict] = []
    prefetch: dict[int, FetchedBytes] = {}
    try:
        for idx, row in enumerate(rows):
            if harvest_client is not None and idx % download_window == 0:
                prefetch = _prefetch_window(
                    session,
                    rows[idx : idx + download_window],
                    client=harvest_client,
                    concurrency=concurrency,
                )
                if sleep > 0:
                    time.sleep(sleep)
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
                    prefetched=prefetch.get(image_id),
                    dedup=dedup,
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

            if use_bulk:
                # Capture the new field values and detach the ORM row so the commit
                # flush won't re-issue a per-row UPDATE; the bulk statement persists it.
                pending_updates.append(_image_update_row(row))
                session.expunge(row)

            update_cursor(session, job, {"last_image_id": image_id})
            if (idx + 1) % commit_every == 0:
                if use_bulk:
                    _bulk_apply_image_updates(session, pending_updates)
                    pending_updates.clear()
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
            if sleep > 0 and download_window == 0:
                time.sleep(sleep)
    finally:
        if harvest_client is not None:
            harvest_client.close()

    if use_bulk and pending_updates:
        _bulk_apply_image_updates(session, pending_updates)
        pending_updates.clear()
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
