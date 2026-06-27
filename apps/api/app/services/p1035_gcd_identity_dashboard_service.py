"""P103.5 GCD identity backfill dashboard — jobs and orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import CatalogImportJob
from app.services.catalog_import_job_service import complete_job, fail_job, record_created, record_failed, start_job
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.gcd_catalog_import_dashboard_service import resolve_cache_path, resolve_gcd_path
from app.services.p103_gcd_catalog_enrichment_service import (
    MAX_ENRICHMENT_WRITE_LIMIT,
    EnrichmentFilters,
    validate_enrichment_filters,
)
from app.services.p103_gcd_enrichment_dashboard_service import enrichment_job_to_dict, p103_status_dict
from app.services.p1035_gcd_identity_backfill_service import (
    P1035_JOB_TYPE_DRY_RUN,
    P1035_JOB_TYPE_WRITE,
    load_resume_catalog_issue_ids,
    run_p1035_identity_dryrun,
    run_p1035_identity_write,
)
from app.services.p1035_gcd_identity_rollback_service import rollback_p1035_identity_job

P1035_JOB_TYPES = (P1035_JOB_TYPE_DRY_RUN, P1035_JOB_TYPE_WRITE)


def list_p1035_identity_jobs(session: Session, *, limit: int = 30) -> list[dict[str, Any]]:
    rows = session.exec(
        select(CatalogImportJob)
        .where(CatalogImportJob.source == GCD_SOURCE)
        .where(CatalogImportJob.job_type.in_(P1035_JOB_TYPES))
        .order_by(CatalogImportJob.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [enrichment_job_to_dict(row) for row in rows]


def load_p1035_identity_job(session: Session, job_id: int) -> dict[str, Any]:
    row = session.get(CatalogImportJob, job_id)
    if row is None:
        raise ValueError(f"catalog_import_job id={job_id} not found")
    if row.job_type not in P1035_JOB_TYPES:
        raise ValueError(f"Job {job_id} is not a P103.5 identity backfill job")
    return enrichment_job_to_dict(row)


def run_p1035_dry_run_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    benchmark: bool = False,
    resume_job_id: int | None = None,
) -> CatalogImportJob:
    skip_ids: set[int] = set()
    if resume_job_id is not None:
        skip_ids = load_resume_catalog_issue_ids(session, resume_job_id)
    job = start_job(
        session,
        source=GCD_SOURCE,
        job_type=P1035_JOB_TYPE_DRY_RUN,
        config={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "dry_run": True,
            "resume_job_id": resume_job_id,
        },
        dry_run=True,
    )
    try:
        report = run_p1035_identity_dryrun(
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            benchmark=benchmark,
            skip_issue_ids=skip_ids,
        )
        report_json = report.to_json()
        job.config = {**(job.config or {}), "report": report_json}
        job.total_seen = report.existing_issues_scanned
        job.total_skipped = report.ambiguous_skipped + report.duplicate_cv_conflicts
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


def run_p1035_write_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    confirm_write: str,
    resume_job_id: int | None = None,
) -> CatalogImportJob:
    validate_enrichment_filters(
        write_batch=True,
        limit=filters.limit,
        publisher=filters.publisher,
        year=filters.year_from if filters.year_from == filters.year_to else None,
        year_from=None if filters.year_from == filters.year_to else filters.year_from,
        year_to=None if filters.year_from == filters.year_to else filters.year_to,
        confirm_write=confirm_write,
        all_catalog=filters.all_catalog,
    )
    skip_ids: set[int] = set()
    if resume_job_id is not None:
        skip_ids = load_resume_catalog_issue_ids(session, resume_job_id)
    job = start_job(
        session,
        source=GCD_SOURCE,
        job_type=P1035_JOB_TYPE_WRITE,
        config={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "confirm_write": confirm_write,
            "resume_job_id": resume_job_id,
        },
        dry_run=False,
    )
    rollback_payload: dict[str, Any] = {"upc_ids": [], "issue_snapshots": []}
    try:
        report = run_p1035_identity_write(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            rollback_collector=rollback_payload,
            skip_issue_ids=skip_ids,
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


def p1035_status_dict() -> dict[str, Any]:
    base = p103_status_dict()
    base["max_write_batch_limit"] = MAX_ENRICHMENT_WRITE_LIMIT
    return base


__all__ = [
    "list_p1035_identity_jobs",
    "load_p1035_identity_job",
    "run_p1035_dry_run_job",
    "run_p1035_write_job",
    "p1035_status_dict",
    "rollback_p1035_identity_job",
]
