"""P97 catalog import job tracking — resumable batch imports.

External source ingestion must comply with each provider's terms of service.
Use polite rate limits and backoff; do not bypass access controls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import CatalogImportError, CatalogImportJob, utc_now


@dataclass
class ImportJobSummary:
    job_id: int
    source: str
    job_type: str
    status: str
    total_seen: int
    total_created: int
    total_updated: int
    total_skipped: int
    total_failed: int
    cursor: dict | None


def start_job(
    session: Session,
    *,
    source: str,
    job_type: str,
    config: dict | None = None,
    cursor: dict | None = None,
    dry_run: bool = False,
) -> CatalogImportJob:
    cfg = dict(config or {})
    cfg["dry_run"] = dry_run
    row = CatalogImportJob(
        source=source,
        job_type=job_type,
        status="running",
        started_at=utc_now(),
        cursor=cursor or {},
        config=cfg,
    )
    session.add(row)
    session.flush()
    return row


def update_cursor(session: Session, job: CatalogImportJob, cursor: dict) -> None:
    job.cursor = cursor
    job.updated_at = utc_now()
    session.add(job)


def record_created(session: Session, job: CatalogImportJob, count: int = 1) -> None:
    job.total_created += count
    job.total_seen += count
    job.updated_at = utc_now()
    session.add(job)


def record_updated(session: Session, job: CatalogImportJob, count: int = 1) -> None:
    job.total_updated += count
    job.total_seen += count
    job.updated_at = utc_now()
    session.add(job)


def record_skipped(session: Session, job: CatalogImportJob, count: int = 1) -> None:
    job.total_skipped += count
    job.total_seen += count
    job.updated_at = utc_now()
    session.add(job)


def record_failed(
    session: Session,
    job: CatalogImportJob,
    *,
    source: str,
    external_id: str | None,
    record_type: str | None,
    error_type: str | None,
    error_message: str,
    raw_payload: dict | None = None,
) -> None:
    job.total_failed += 1
    job.total_seen += 1
    job.last_error = error_message[:2000]
    job.updated_at = utc_now()
    session.add(job)
    session.add(
        CatalogImportError(
            job_id=int(job.id or 0),
            source=source,
            external_id=external_id,
            record_type=record_type,
            error_type=error_type,
            error_message=error_message,
            raw_payload=raw_payload,
        )
    )


def complete_job(session: Session, job: CatalogImportJob) -> ImportJobSummary:
    job.status = "completed"
    job.completed_at = utc_now()
    job.updated_at = utc_now()
    session.add(job)
    session.flush()
    return job_summary(job)


def fail_job(session: Session, job: CatalogImportJob, error: str) -> ImportJobSummary:
    job.status = "failed"
    job.last_error = error[:2000]
    job.completed_at = utc_now()
    job.updated_at = utc_now()
    session.add(job)
    session.flush()
    return job_summary(job)


def resume_latest_job(session: Session, *, source: str, job_type: str) -> CatalogImportJob | None:
    rows = session.exec(
        select(CatalogImportJob)
        .where(CatalogImportJob.source == source)
        .where(CatalogImportJob.job_type == job_type)
        .order_by(CatalogImportJob.id.desc())
    ).all()
    for row in rows:
        if row.status in ("running", "pending"):
            return row
    return None


def comicvine_volume_import_scope(
    *,
    publisher_filter: str | None = None,
    series_name: str | None = None,
    strict_publisher: bool = False,
    import_issues: bool = False,
    allow_international_editions: bool = False,
) -> dict[str, str | bool]:
    """Normalized scope for ComicVine volume import jobs (cursor + resume identity)."""
    return {
        "publisher_filter": (publisher_filter or "").strip(),
        "series_name": (series_name or "").strip(),
        "strict_publisher": bool(strict_publisher),
        "import_issues": bool(import_issues),
        "allow_international_editions": bool(allow_international_editions),
    }


def comicvine_issue_import_scope(
    *,
    publisher_filter: str | None = None,
    series_name: str | None = None,
    strict_publisher: bool = False,
    allow_international_editions: bool = False,
) -> dict[str, str | bool]:
    return {
        **comicvine_volume_import_scope(
            publisher_filter=publisher_filter,
            series_name=series_name,
            strict_publisher=strict_publisher,
            import_issues=True,
            allow_international_editions=allow_international_editions,
        ),
        "phase": "volume_issues",
    }


def _job_config_scope(config: dict | None) -> dict[str, str | bool]:
    cfg = config or {}
    return comicvine_volume_import_scope(
        publisher_filter=str(cfg.get("publisher_filter") or ""),
        series_name=str(cfg.get("series_name") or ""),
        strict_publisher=bool(cfg.get("strict_publisher")),
        import_issues=bool(cfg.get("import_issues")),
        allow_international_editions=bool(cfg.get("allow_international_editions")),
    )


def scopes_match(left: dict[str, str | bool] | None, right: dict[str, str | bool] | None) -> bool:
    return _job_config_scope(left if isinstance(left, dict) else None) == _job_config_scope(
        right if isinstance(right, dict) else None
    )


def resume_scoped_job(
    session: Session,
    *,
    source: str,
    job_type: str,
    scope: dict[str, str | bool],
) -> CatalogImportJob | None:
    rows = session.exec(
        select(CatalogImportJob)
        .where(CatalogImportJob.source == source)
        .where(CatalogImportJob.job_type == job_type)
        .order_by(CatalogImportJob.id.desc())
    ).all()
    for row in rows:
        if row.status in ("running", "pending") and scopes_match(row.config, scope):
            return row
    return None


def latest_completed_cursor_for_scope(
    session: Session,
    *,
    source: str,
    job_type: str,
    scope: dict[str, str | bool],
) -> dict | None:
    rows = session.exec(
        select(CatalogImportJob)
        .where(CatalogImportJob.source == source)
        .where(CatalogImportJob.job_type == job_type)
        .order_by(CatalogImportJob.id.desc())
    ).all()
    for row in rows:
        if row.status == "completed" and scopes_match(row.config, scope):
            return dict(row.cursor or {})
    return None


def job_summary(job: CatalogImportJob) -> ImportJobSummary:
    return ImportJobSummary(
        job_id=int(job.id or 0),
        source=job.source,
        job_type=job.job_type,
        status=job.status,
        total_seen=job.total_seen,
        total_created=job.total_created,
        total_updated=job.total_updated,
        total_skipped=job.total_skipped,
        total_failed=job.total_failed,
        cursor=job.cursor,
    )
