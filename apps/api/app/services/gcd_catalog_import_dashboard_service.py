"""GCD catalog import dashboard — matrix, preview, dry-run, and job-backed writes."""

from __future__ import annotations

import csv
import io
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.catalog_p97 import CatalogImportJob
from app.services.catalog_import_job_service import (
    complete_job,
    fail_job,
    record_created,
    record_failed,
    record_skipped,
    start_job,
)
from app.services.gcd_barcode_import_service import GCD_SOURCE, _year_from_key_date, extract_barcodes
from app.services.p101_catalog_cache_service import (
    DEFAULT_CACHE_PATH,
    CatalogCacheContext,
    YEAR_MAX,
    YEAR_MIN,
    export_catalog_cache,
)
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import (
    FOCUS_PUBLISHERS,
    YEAR_EXPR,
    _classify_missing_row,
)
from app.services.p102_gcd_modern_acquisition_write_service import (
    WriteBatchFilters,
    WriteBatchRunOptions,
    run_p102_write_batch,
    validate_write_batch_args,
)

GCD_JOB_SOURCE = GCD_SOURCE
GCD_JOB_TYPE_MATRIX = "gcd_matrix_scan"
GCD_JOB_TYPE_DRY_RUN = "gcd_scope_dry_run"
GCD_JOB_TYPE_WRITE = "gcd_write_batch"
GCD_JOB_TYPE_LARGE_WRITE = "gcd_large_write_batch"

# Calibrated from P102 pilot (~12s / 205k rows scan; ~200s / 100 writes).
SECONDS_PER_GCD_ROW_SCAN = 12.0 / 205_281
SECONDS_PER_WRITE_ROW = 2.0


@dataclass
class GcdImportCellStats:
    publisher: str
    year: int
    gcd_rows: int = 0
    existing_issues: int = 0
    clean_candidates: int = 0
    variants: int = 0
    reprints: int = 0
    foreign_editions: int = 0
    conflicts: int = 0
    low_confidence: int = 0
    barcodes_available: int = 0
    estimated_scan_seconds: float = 0.0
    estimated_write_seconds: float = 0.0

    def finalize_estimates(self) -> None:
        self.estimated_scan_seconds = round(max(self.gcd_rows, 1) * SECONDS_PER_GCD_ROW_SCAN, 1)
        write_rows = min(self.clean_candidates, 100)
        self.estimated_write_seconds = round(write_rows * SECONDS_PER_WRITE_ROW, 1)

    def to_dict(self) -> dict[str, Any]:
        self.finalize_estimates()
        return asdict(self)


@dataclass
class GcdPreviewRow:
    gcd_issue_id: int
    publisher: str
    focus_publisher: str
    series: str
    issue_number: str
    year: int
    key_date: str | None
    barcode: str | None
    classification: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GcdImportMatrixReport:
    generated_at: str
    year_from: int
    year_to: int
    gcd_database: str
    catalog_cache: str
    elapsed_seconds: float
    cells: list[GcdImportCellStats] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "gcd_database": self.gcd_database,
            "catalog_cache": self.catalog_cache,
            "elapsed_seconds": self.elapsed_seconds,
            "cells": [c.to_dict() for c in self.cells],
        }


def resolve_gcd_path(override: str | None = None) -> Path:
    if override and str(override).strip():
        return Path(override).expanduser()
    return get_settings().gcd_sqlite_path


def resolve_cache_path(override: str | None = None) -> Path:
    if override and str(override).strip():
        return Path(override).expanduser()
    return DEFAULT_CACHE_PATH


def ensure_catalog_cache(session: Session, cache_path: Path, *, refresh: bool = False) -> None:
    if refresh or not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        export_catalog_cache(session, cache_path)


def _cell_key(publisher: str, year: int) -> tuple[str, int]:
    return publisher, year


def _scan_gcd_rows(
    *,
    gcd_path: Path,
    ctx: CatalogCacheContext,
    year_from: int,
    year_to: int,
    publisher_filter: str | None = None,
    collect_preview: list[GcdPreviewRow] | None = None,
    preview_limit: int = 100,
    preview_class: str = "clean_primary_candidate",
) -> dict[tuple[str, int], GcdImportCellStats]:
    cells: dict[tuple[str, int], GcdImportCellStats] = {}
    seen_gcd_keys: Counter[tuple[str, str, str]] = Counter()

    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(
        f"""
        SELECT i.id, p.name, s.name, i.number, i.barcode, i.key_date, s.year_began
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        """,
        (year_from, year_to),
    )

    while True:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for gcd_issue_id, publisher, series, number, barcode, key_date, year_began in batch:
            year_val = _year_from_key_date(key_date, year_began)
            if year_val is None:
                continue
            year = int(year_val)
            focus = canonical_focus_publisher_label(str(publisher or ""))
            if focus is None or focus not in FOCUS_PUBLISHERS:
                continue
            if publisher_filter and focus != publisher_filter:
                continue

            key = _cell_key(focus, year)
            cell = cells.get(key)
            if cell is None:
                cell = GcdImportCellStats(publisher=focus, year=year)
                cells[key] = cell
            cell.gcd_rows += 1

            if ctx.matcher.matches(
                publisher=str(publisher or focus),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
            ):
                cell.existing_issues += 1
                continue

            barcodes = extract_barcodes(barcode)
            cls, reason, best_bc, project_issue, project_upc = _classify_missing_row(
                focus_label=focus,
                publisher_raw=str(publisher or ""),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
                barcode_raw=str(barcode) if barcode else None,
                barcodes=barcodes,
                ctx=ctx,
                seen_gcd_keys=seen_gcd_keys,
            )

            if cls == "clean_primary_candidate":
                cell.clean_candidates += 1
                if project_upc and best_bc:
                    cell.barcodes_available += 1
            elif cls == "variant_candidate":
                cell.variants += 1
            elif cls == "reprint_or_digest":
                cell.reprints += 1
            elif cls == "foreign_or_international":
                cell.foreign_editions += 1
            elif cls == "duplicate_or_conflict":
                cell.conflicts += 1
            elif cls == "low_confidence":
                cell.low_confidence += 1

            if collect_preview is not None and cls == preview_class and len(collect_preview) < preview_limit:
                collect_preview.append(
                    GcdPreviewRow(
                        gcd_issue_id=int(gcd_issue_id),
                        publisher=str(publisher or ""),
                        focus_publisher=focus,
                        series=str(series or ""),
                        issue_number=str(number or ""),
                        year=year,
                        key_date=str(key_date) if key_date else None,
                        barcode=best_bc,
                        classification=cls,
                        reason=reason,
                    )
                )

    conn.close()
    return cells


def build_gcd_import_matrix(
    *,
    gcd_path: Path,
    cache_path: Path,
    year_from: int = YEAR_MIN,
    year_to: int = YEAR_MAX,
) -> GcdImportMatrixReport:
    t0 = time.perf_counter()
    ctx = CatalogCacheContext.load(cache_path)
    cells_map = _scan_gcd_rows(
        gcd_path=gcd_path,
        ctx=ctx,
        year_from=year_from,
        year_to=year_to,
    )
    cells = sorted(cells_map.values(), key=lambda c: (c.publisher, c.year))
    return GcdImportMatrixReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        year_from=year_from,
        year_to=year_to,
        gcd_database=str(gcd_path),
        catalog_cache=str(cache_path),
        elapsed_seconds=round(time.perf_counter() - t0, 2),
        cells=cells,
    )


def analyze_gcd_scope(
    *,
    gcd_path: Path,
    cache_path: Path,
    publisher: str,
    year: int,
    preview_limit: int = 100,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    ctx = CatalogCacheContext.load(cache_path)
    preview: list[GcdPreviewRow] = []
    cells = _scan_gcd_rows(
        gcd_path=gcd_path,
        ctx=ctx,
        year_from=year,
        year_to=year,
        publisher_filter=publisher,
        collect_preview=preview,
        preview_limit=preview_limit,
    )
    cell = cells.get(_cell_key(publisher, year))
    if cell is None:
        cell = GcdImportCellStats(publisher=publisher, year=year)
    return {
        "publisher": publisher,
        "year": year,
        "stats": cell.to_dict(),
        "preview_rows": [r.to_dict() for r in preview],
        "elapsed_seconds": round(time.perf_counter() - t0, 2),
        "gcd_database": str(gcd_path),
        "catalog_cache": str(cache_path),
    }


def preview_rows_to_csv(rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def job_to_dashboard_dict(job: CatalogImportJob) -> dict[str, Any]:
    cfg = dict(job.config or {})
    report = dict(cfg.get("report") or {})
    rollback = dict(cfg.get("rollback") or {})
    stats = dict(cfg.get("scope_stats") or {})
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
        "inserted_issues": job.total_created,
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
        "scope_stats": stats,
        "report": report,
        "rollback": rollback,
    }


def load_job_dashboard_dict(session: Session, job_id: int) -> dict[str, Any]:
    """Load job row in-session and build a JSON-safe dashboard payload."""
    row = session.get(CatalogImportJob, job_id)
    if row is None:
        raise ValueError(f"catalog_import_job id={job_id} not found")
    return job_to_dashboard_dict(row)


def list_gcd_import_jobs(session: Session, *, limit: int = 30) -> list[dict[str, Any]]:
    rows = session.exec(
        select(CatalogImportJob)
        .where(CatalogImportJob.source == GCD_JOB_SOURCE)
        .order_by(CatalogImportJob.id.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [job_to_dashboard_dict(row) for row in rows]


def run_matrix_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    year_from: int,
    year_to: int,
) -> CatalogImportJob:
    job = start_job(
        session,
        source=GCD_JOB_SOURCE,
        job_type=GCD_JOB_TYPE_MATRIX,
        config={"year_from": year_from, "year_to": year_to, "dry_run": True},
        dry_run=True,
    )
    try:
        matrix = build_gcd_import_matrix(
            gcd_path=gcd_path,
            cache_path=cache_path,
            year_from=year_from,
            year_to=year_to,
        )
        payload = matrix.to_dict()
        job.config = {**(job.config or {}), "report": payload}
        job.total_seen = sum(c.gcd_rows for c in matrix.cells)
        job.total_skipped = sum(c.existing_issues for c in matrix.cells)
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


def run_scope_dry_run_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    publisher: str,
    year: int,
    preview_limit: int = 100,
) -> CatalogImportJob:
    job = start_job(
        session,
        source=GCD_JOB_SOURCE,
        job_type=GCD_JOB_TYPE_DRY_RUN,
        config={
            "publisher": publisher,
            "year_from": year,
            "year_to": year,
            "dry_run": True,
            "preview_limit": preview_limit,
        },
        dry_run=True,
    )
    try:
        analysis = analyze_gcd_scope(
            gcd_path=gcd_path,
            cache_path=cache_path,
            publisher=publisher,
            year=year,
            preview_limit=preview_limit,
        )
        stats = analysis.get("stats") or {}
        job.config = {
            **(job.config or {}),
            "scope_stats": stats,
            "report": analysis,
        }
        job.total_seen = int(stats.get("gcd_rows") or 0)
        job.total_skipped = int(stats.get("existing_issues") or 0)
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


def run_gcd_write_batch_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: WriteBatchFilters,
    confirm_write: str,
) -> CatalogImportJob:
    validate_write_batch_args(
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
        source=GCD_JOB_SOURCE,
        job_type=GCD_JOB_TYPE_WRITE,
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
    rollback_issue_ids: list[int] = []
    rollback_upc_ids: list[int] = []
    rollback_variant_ids: list[int] = []
    try:
        report = run_p102_write_batch(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            rollback_collector={
                "issue_ids": rollback_issue_ids,
                "upc_ids": rollback_upc_ids,
                "variant_ids": rollback_variant_ids,
            },
        )
        report_json = report.to_json()
        for err in report.errors:
            record_failed(
                session,
                job,
                source=GCD_JOB_SOURCE,
                external_id=None,
                record_type="catalog_issue",
                error_type="write_error",
                error_message=err,
            )
        record_created(session, job, count=report.inserted_issues)
        job.config = {
            **(job.config or {}),
            "report": report_json,
            "inserted_upcs": report.inserted_upcs,
            "rollback": {
                "issue_ids": rollback_issue_ids,
                "upc_ids": rollback_upc_ids,
                "variant_ids": rollback_variant_ids,
            },
        }
        job.total_skipped = report.skipped_existing + report.skipped_conflicts
        session.add(job)
        session.flush()
        if report.errors and report.inserted_issues == 0:
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


def run_gcd_large_write_batch_job(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: WriteBatchFilters,
    confirm_write: str,
    progress_interval: int = 250,
    max_errors: int = 25,
    commit_batch_size: int = 250,
    benchmark: bool = False,
    resume_job_id: int | None = None,
    use_fast_path: bool = True,
) -> CatalogImportJob:
    validate_write_batch_args(
        write_batch=True,
        limit=filters.limit,
        publisher=filters.publisher,
        year=None if filters.year_from != filters.year_to else filters.year_from,
        year_from=filters.year_from if filters.year_from != filters.year_to else None,
        year_to=filters.year_to if filters.year_from != filters.year_to else None,
        confirm_write=confirm_write,
        large_batch=True,
    )
    print("catalog_import_job: creating gcd_large_write_batch job...", flush=True)
    job = start_job(
        session,
        source=GCD_JOB_SOURCE,
        job_type=GCD_JOB_TYPE_LARGE_WRITE,
        config={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "dry_run": False,
            "confirm_write": confirm_write,
            "progress_interval": progress_interval,
            "max_errors": max_errors,
            "refresh_cache": False,
            "fast_path": use_fast_path,
            "commit_batch_size": commit_batch_size,
            "benchmark": benchmark,
            "resume_job_id": resume_job_id,
        },
        dry_run=False,
    )
    rollback_issue_ids: list[int] = []
    rollback_upc_ids: list[int] = []
    rollback_variant_ids: list[int] = []
    write_t0 = time.perf_counter()
    try:
        if use_fast_path:
            from app.services.p102_gcd_write_batch_fast import (
                WriteBatchRunOptionsFast,
                enrich_report_with_perf,
                run_p102_write_batch_fast,
            )

            report, timer = run_p102_write_batch_fast(
                session,
                gcd_path=gcd_path,
                cache_path=cache_path,
                filters=filters,
                rollback_collector={
                    "issue_ids": rollback_issue_ids,
                    "upc_ids": rollback_upc_ids,
                    "variant_ids": rollback_variant_ids,
                },
                run_options=WriteBatchRunOptionsFast(
                    progress_interval=progress_interval,
                    max_errors=max_errors,
                    log_progress=True,
                    stage_log=lambda msg: print(msg, flush=True),
                    commit_batch_size=commit_batch_size,
                    benchmark=benchmark,
                    resume_job_id=resume_job_id,
                ),
            )
            elapsed_write = time.perf_counter() - write_t0
            report_json = enrich_report_with_perf(report, timer, elapsed_write)
        else:
            report = run_p102_write_batch(
                session,
                gcd_path=gcd_path,
                cache_path=cache_path,
                filters=filters,
                rollback_collector={
                    "issue_ids": rollback_issue_ids,
                    "upc_ids": rollback_upc_ids,
                    "variant_ids": rollback_variant_ids,
                },
                run_options=WriteBatchRunOptions(
                    progress_interval=progress_interval,
                    max_errors=max_errors,
                    log_progress=True,
                    stage_log=lambda msg: print(msg, flush=True),
                ),
            )
            report_json = report.to_json()
        for err in report.errors:
            record_failed(
                session,
                job,
                source=GCD_JOB_SOURCE,
                external_id=None,
                record_type="catalog_issue",
                error_type="write_error",
                error_message=err,
            )
        record_created(session, job, count=report.inserted_issues)
        job.config = {
            **(job.config or {}),
            "report": report_json,
            "inserted_upcs": report.inserted_upcs,
            "rollback_id": int(job.id or 0),
            "rollback": {
                "issue_ids": rollback_issue_ids,
                "upc_ids": rollback_upc_ids,
                "variant_ids": rollback_variant_ids,
            },
        }
        job.total_skipped = report.skipped_existing + report.skipped_conflicts
        session.add(job)
        session.flush()
        if report.stopped_early or (report.errors and report.inserted_issues == 0):
            fail_job(session, job, report.stop_reason or (report.errors[0] if report.errors else "stopped"))
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


def count_clean_candidates_for_scope(
    *,
    gcd_path: Path,
    cache_path: Path,
    publisher: str,
    year_from: int,
    year_to: int,
) -> int:
    ctx = CatalogCacheContext.load(cache_path)
    cells = _scan_gcd_rows(
        gcd_path=gcd_path,
        ctx=ctx,
        year_from=year_from,
        year_to=year_to,
        publisher_filter=publisher,
    )
    return sum(c.clean_candidates for c in cells.values())


@dataclass
class GcdRemainingPublisherStats:
    publisher: str
    year_from: int
    year_to: int
    remaining_clean_candidates: int
    already_in_comicos: int
    total_clean_primary: int
    gcd_rows_in_scope: int
    variants: int
    reprints: int
    foreign_editions: int
    conflicts: int
    low_confidence: int
    barcodes_available: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_gcd_remaining_stats(
    *,
    gcd_path: Path,
    cache_path: Path,
    publisher: str,
    year_from: int,
    year_to: int,
) -> GcdRemainingPublisherStats:
    """Remaining importable clean rows vs already-matched catalog rows (same scan as import matrix)."""
    ctx = CatalogCacheContext.load(cache_path)
    cells = _scan_gcd_rows(
        gcd_path=gcd_path,
        ctx=ctx,
        year_from=year_from,
        year_to=year_to,
        publisher_filter=publisher,
    )
    remaining = sum(c.clean_candidates for c in cells.values())
    already = sum(c.existing_issues for c in cells.values())
    return GcdRemainingPublisherStats(
        publisher=publisher,
        year_from=year_from,
        year_to=year_to,
        remaining_clean_candidates=remaining,
        already_in_comicos=already,
        total_clean_primary=remaining + already,
        gcd_rows_in_scope=sum(c.gcd_rows for c in cells.values()),
        variants=sum(c.variants for c in cells.values()),
        reprints=sum(c.reprints for c in cells.values()),
        foreign_editions=sum(c.foreign_editions for c in cells.values()),
        conflicts=sum(c.conflicts for c in cells.values()),
        low_confidence=sum(c.low_confidence for c in cells.values()),
        barcodes_available=sum(c.barcodes_available for c in cells.values()),
    )
