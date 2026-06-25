"""P103 GCD enrichment dashboard — dry-run, pilot write, jobs, rollback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.catalog_p97 import CatalogImportJob
from app.services.catalog_import_job_service import complete_job, fail_job, record_created, record_failed, start_job
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.gcd_catalog_import_dashboard_service import (
    ensure_catalog_cache,
    resolve_cache_path,
    resolve_gcd_path,
)
from app.services.p103_gcd_catalog_enrichment_service import (
    EnrichmentFilters,
    P103_JOB_TYPE_DRY_RUN,
    P103_JOB_TYPE_WRITE,
    MAX_ENRICHMENT_WRITE_LIMIT,
    run_p103_enrichment_dryrun,
    validate_enrichment_filters,
)
from app.services.p103_gcd_enrichment_write_service import run_p103_enrichment_write_batch

P103_ENRICHMENT_JOB_TYPES = (P103_JOB_TYPE_DRY_RUN, P103_JOB_TYPE_WRITE)


def enrichment_job_to_dict(job: CatalogImportJob) -> dict[str, Any]:
    cfg = dict(job.config or {})
    report = dict(cfg.get("report") or {})
    rollback = dict(cfg.get("rollback") or {})
    return {
        "job_id": int(job.id or 0),
        "rollback_id": int(job.id or 0),
        "source": job.source,
        "job_type": job.job_type,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "total_seen": job.total_seen,
        "updated_issues": int(report.get("updated_issues") or job.total_created or 0),
        "inserted_upcs": int(report.get("inserted_upcs") or cfg.get("inserted_upcs") or 0),
        "skipped": job.total_skipped,
        "errors": int(job.total_failed),
        "last_error": job.last_error,
        "scope": {
            "publisher": cfg.get("publisher"),
            "year_from": cfg.get("year_from"),
            "year_to": cfg.get("year_to"),
            "limit": cfg.get("limit"),
            "dry_run": bool(cfg.get("dry_run")),
        },
        "report": report,
        "rollback": rollback,
    }


def list_p103_enrichment_jobs(session: Session, *, limit: int = 30) -> list[dict[str, Any]]:
    rows = session.exec(
        select(CatalogImportJob)
        .where(CatalogImportJob.source == GCD_SOURCE)
        .where(CatalogImportJob.job_type.in_(P103_ENRICHMENT_JOB_TYPES))
        .order_by(CatalogImportJob.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [enrichment_job_to_dict(row) for row in rows]


def load_p103_enrichment_job(session: Session, job_id: int) -> dict[str, Any]:
    row = session.get(CatalogImportJob, job_id)
    if row is None:
        raise ValueError(f"catalog_import_job id={job_id} not found")
    if row.job_type not in P103_ENRICHMENT_JOB_TYPES:
        raise ValueError(f"Job {job_id} is not a P103 enrichment job")
    return enrichment_job_to_dict(row)


def run_p103_dry_run_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
) -> CatalogImportJob:
    job = start_job(
        session,
        source=GCD_SOURCE,
        job_type=P103_JOB_TYPE_DRY_RUN,
        config={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "dry_run": True,
        },
        dry_run=True,
    )
    try:
        report = run_p103_enrichment_dryrun(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            benchmark=False,
        )
        report_json = report.to_json()
        job.config = {**(job.config or {}), "report": report_json}
        job.total_seen = report.matched_to_gcd
        job.total_skipped = report.skipped_no_catalog_match
        session.add(job)
        session.flush()
        complete_job(session, job)
        session.commit()
    except Exception as exc:
        session.rollback()
        job = session.get(CatalogImportJob, job.id)
        if job:
            fail_job(session, job, str(exc))
            session.commit()
        raise
    return job


def run_p103_write_batch_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    confirm_write: str,
) -> CatalogImportJob:
    validate_enrichment_filters(
        write_batch=True,
        limit=filters.limit,
        publisher=filters.publisher,
        year=filters.year_from if filters.year_from == filters.year_to else None,
        year_from=None if filters.year_from == filters.year_to else filters.year_from,
        year_to=None if filters.year_from == filters.year_to else filters.year_to,
        confirm_write=confirm_write,
    )
    job = start_job(
        session,
        source=GCD_SOURCE,
        job_type=P103_JOB_TYPE_WRITE,
        config={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "dry_run": False,
            "confirm_write": confirm_write,
        },
        dry_run=False,
    )
    rollback_payload: dict[str, Any] = {"upc_ids": [], "issue_snapshots": []}
    try:
        report = run_p103_enrichment_write_batch(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            rollback_collector=rollback_payload,
        )
        report_json = report.to_json()
        for err in report.errors:
            record_failed(
                session,
                job,
                source=GCD_SOURCE,
                external_id=None,
                record_type="catalog_issue",
                error_type="write_error",
                error_message=err,
            )
        record_created(session, job, count=report.updated_issues)
        job.config = {
            **(job.config or {}),
            "report": report_json,
            "inserted_upcs": report.inserted_upcs,
            "rollback": rollback_payload,
            "rollback_id": int(job.id or 0),
        }
        job.total_skipped = report.skipped_no_updates + report.skipped_conflicts
        session.add(job)
        session.flush()
        if report.errors and report.updated_issues == 0:
            fail_job(session, job, report.errors[0])
        else:
            complete_job(session, job)
        session.commit()
    except Exception as exc:
        session.rollback()
        job = session.get(CatalogImportJob, job.id)
        if job:
            fail_job(session, job, str(exc))
            session.commit()
        raise
    return job


def p103_status_dict() -> dict[str, Any]:
    gcd_path = resolve_gcd_path()
    cache_path = resolve_cache_path()
    settings = get_settings()
    from app.services.p101_catalog_cache_service import YEAR_MAX, YEAR_MIN
    from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS

    return {
        "gcd_database": str(gcd_path),
        "gcd_database_exists": gcd_path.exists(),
        "catalog_cache": str(cache_path),
        "catalog_cache_exists": cache_path.exists(),
        "gcd_enrichment_enabled": settings.gcd_enrichment_enabled,
        "max_write_batch_limit": MAX_ENRICHMENT_WRITE_LIMIT,
        "focus_publishers": list(FOCUS_PUBLISHERS),
        "default_year_from": YEAR_MIN,
        "default_year_to": YEAR_MAX,
    }
