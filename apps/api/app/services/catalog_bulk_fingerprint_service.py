from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, utc_now
from app.services.catalog_bulk_enrichment_selection import (
    count_missing_fingerprints,
    count_ready_covers,
    count_valid_fingerprints_on_ready_covers,
    select_ready_covers_needing_fingerprint,
)
from app.services.catalog_cover_harvest_service import (
    resolve_catalog_image_local_path,
    resolve_catalog_image_local_path_fast,
)
from app.services.catalog_fingerprint_service import fingerprint_image_path
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


def _hash_path(path: str) -> tuple[str, str, str] | None:
    try:
        return fingerprint_image_path(path)
    except Exception:  # noqa: BLE001 - per-image failure recorded by caller
        return None


def _resolve_work_items(session: Session, images: list[CatalogImage]) -> list[tuple[int, str, int | None, int | None]]:
    items: list[tuple[int, str, int | None, int | None]] = []
    for image in images:
        resolved = resolve_catalog_image_local_path_fast(image)
        if resolved is None:
            resolved = resolve_catalog_image_local_path(session, image)
        if resolved is None:
            continue
        items.append((int(image.id or 0), str(resolved), image.issue_id, image.variant_id))
    return items


def _parallel_hash_items(
    items: list[tuple[int, str, int | None, int | None]],
    *,
    concurrency: int,
) -> tuple[list[dict], list[tuple[int, str]]]:
    """Return (rows ready for upsert, (image_id, error) failures)."""
    if not items:
        return [], []
    workers = max(1, int(concurrency))
    now = utc_now()
    upsert_rows: list[dict] = []
    failures: list[tuple[int, str]] = []

    if workers == 1:
        for iid, path, issue_id, variant_id in items:
            hashes = _hash_path(path)
            if hashes is None:
                failures.append((iid, "hash failed"))
                continue
            ph, dh, ah = hashes
            upsert_rows.append(
                {
                    "image_id": iid,
                    "issue_id": issue_id,
                    "variant_id": variant_id,
                    "phash": ph,
                    "dhash": dh,
                    "ahash": ah,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        return upsert_rows, failures

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_hash_path, path): (iid, issue_id, variant_id) for iid, path, issue_id, variant_id in items
        }
        for future in as_completed(future_map):
            iid, issue_id, variant_id = future_map[future]
            try:
                hashes = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append((iid, str(exc)[:500]))
                continue
            if hashes is None:
                failures.append((iid, "hash failed"))
                continue
            ph, dh, ah = hashes
            upsert_rows.append(
                {
                    "image_id": iid,
                    "issue_id": issue_id,
                    "variant_id": variant_id,
                    "phash": ph,
                    "dhash": dh,
                    "ahash": ah,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    return upsert_rows, failures


def _bulk_upsert_fingerprints(session: Session, rows: list[dict]) -> None:
    """One round-trip upsert for a batch (Postgres)."""
    if not rows:
        return
    value_rows: list[str] = []
    params: dict = {}
    for k, row in enumerate(rows):
        value_rows.append(
            f"(:image_id_{k}, :issue_id_{k}, :variant_id_{k}, :phash_{k}, :dhash_{k}, :ahash_{k}, :created_at_{k}, :updated_at_{k})"
        )
        params[f"image_id_{k}"] = row["image_id"]
        params[f"issue_id_{k}"] = row.get("issue_id")
        params[f"variant_id_{k}"] = row.get("variant_id")
        params[f"phash_{k}"] = row.get("phash")
        params[f"dhash_{k}"] = row.get("dhash")
        params[f"ahash_{k}"] = row.get("ahash")
        params[f"created_at_{k}"] = row["created_at"]
        params[f"updated_at_{k}"] = row["updated_at"]
    sql = text(
        "INSERT INTO catalog_image_fingerprint "
        "(image_id, issue_id, variant_id, phash, dhash, ahash, created_at, updated_at) "
        f"VALUES {', '.join(value_rows)} "
        "ON CONFLICT (image_id) DO UPDATE SET "
        "issue_id = EXCLUDED.issue_id, "
        "variant_id = EXCLUDED.variant_id, "
        "phash = EXCLUDED.phash, "
        "dhash = EXCLUDED.dhash, "
        "ahash = EXCLUDED.ahash, "
        "updated_at = EXCLUDED.updated_at"
    )
    session.connection().execute(sql, params)


def run_bulk_fingerprints(
    session: Session,
    *,
    missing_only: bool = True,
    limit: int = 200,
    dry_run: bool = False,
    resume: bool = False,
    batch_size: int = 25,
    concurrency: int = 8,
) -> dict:
    commit_every = max(1, int(batch_size))
    workers = max(1, int(concurrency))
    use_bulk = (not dry_run) and session.connection().dialect.name == "postgresql"

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

    LOGGER.info("fingerprint_batch counting ready covers and missing fingerprints...")
    ready_covers_available = count_ready_covers(session)
    missing_fingerprints_available = count_missing_fingerprints(session)
    LOGGER.info(
        "fingerprint_batch selecting up to %s covers (ready=%s missing_fp=%s)...",
        limit,
        ready_covers_available,
        missing_fingerprints_available,
    )

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
        "fingerprint_batch starting job_id=%s batch=%s concurrency=%s ready=%s missing=%s selected=%s",
        job.id,
        commit_every,
        workers,
        ready_covers_available,
        missing_fingerprints_available,
        selected_for_fingerprint_batch,
    )

    processed = 0

    for start in range(0, len(rows), commit_every):
        window = rows[start : start + commit_every]
        work = _resolve_work_items(session, window)
        upsert_rows, hash_failures = _parallel_hash_items(work, concurrency=workers)

        for iid_fail, msg in hash_failures:
            record_failed(
                session,
                job,
                source="INTERNAL",
                external_id=str(iid_fail),
                record_type="fingerprint",
                error_type="processing",
                error_message=msg,
            )

        unresolved = len(window) - len(work)
        for _ in range(unresolved):
            record_skipped(session, job)

        if dry_run:
            processed += len(upsert_rows)
            for _ in upsert_rows:
                record_updated(session, job)
        elif use_bulk:
            _bulk_upsert_fingerprints(session, upsert_rows)
            processed += len(upsert_rows)
            for _ in upsert_rows:
                record_updated(session, job)
        else:
            from app.services.catalog_fingerprint_service import fingerprint_catalog_image

            for image_id, _path, _, _ in work:
                try:
                    row = fingerprint_catalog_image(session, image_id, dry_run=False)
                    if row is None or not (row.phash or row.dhash or row.ahash):
                        record_skipped(session, job)
                    else:
                        record_updated(session, job)
                        processed += 1
                except Exception as exc:  # noqa: BLE001
                    record_failed(
                        session,
                        job,
                        source="INTERNAL",
                        external_id=str(image_id),
                        record_type="fingerprint",
                        error_type="processing",
                        error_message=str(exc),
                    )

        last_in_window = int(window[-1].id or 0)
        update_cursor(session, job, {"last_image_id": last_in_window})
        _flush(session, dry_run=dry_run)
        LOGGER.info(
            "fingerprint progress %s/%s image_id=%s job_updated=%s job_failed=%s",
            min(start + commit_every, len(rows)),
            len(rows),
            last_in_window,
            job.total_updated,
            job.total_failed,
        )

    _flush(session, dry_run=dry_run)
    summary = complete_job(session, job)
    _flush(session, dry_run=dry_run)
    LOGGER.info("fingerprint batch complete updated=%s failed=%s", summary.total_updated, summary.total_failed)
    return {**summary.__dict__, **fingerprint_coverage(session)}
