"""High-throughput P102 GCD write batch (batched commits + preloaded guards + timing)."""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.catalog_p97 import CatalogImportJob
from app.models.intake_queue import ComicIssueBarcode
from app.services.catalog_ingestion_service import (
    merge_external_ids,
    normalize_issue_number,
    normalize_upc,
    upsert_publisher,
    upsert_series,
    utc_now,
)
from app.services.gcd_barcode_import_service import GCD_SOURCE, _year_from_key_date, extract_barcodes
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import YEAR_EXPR, _classify_missing_row
from app.services.p102_gcd_modern_acquisition_write_service import (
    FOCUS_PUBLISHER_NAMES,
    P102WriteBatchReport,
    WriteBatchFilters,
    WriteBatchRunOptions,
    _cover_date_from_key_date,
    _insert_upc_if_absent,
    _stage,
)


@dataclass
class WriteBatchRunOptionsFast(WriteBatchRunOptions):
    commit_batch_size: int = 250
    benchmark: bool = False
    resume_job_id: int | None = None


@dataclass
class WriteBatchTimer:
    preload_sec: float = 0.0
    gcd_scan_classify_sec: float = 0.0
    skip_checks_sec: float = 0.0
    publisher_series_sec: float = 0.0
    issue_insert_sec: float = 0.0
    variant_insert_sec: float = 0.0
    upc_insert_sec: float = 0.0
    commit_sec: float = 0.0
    job_serialize_sec: float = 0.0
    gcd_rows_scanned: int = 0
    commits: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "preload_sec": round(self.preload_sec, 3),
            "gcd_scan_classify_sec": round(self.gcd_scan_classify_sec, 3),
            "skip_checks_sec": round(self.skip_checks_sec, 3),
            "publisher_series_sec": round(self.publisher_series_sec, 3),
            "issue_insert_sec": round(self.issue_insert_sec, 3),
            "variant_insert_sec": round(self.variant_insert_sec, 3),
            "upc_insert_sec": round(self.upc_insert_sec, 3),
            "commit_sec": round(self.commit_sec, 3),
            "job_serialize_sec": round(self.job_serialize_sec, 3),
            "gcd_rows_scanned": self.gcd_rows_scanned,
            "commits": self.commits,
        }

    def summary(self, *, inserted: int, elapsed_total: float) -> dict[str, Any]:
        rows_per_min = (inserted / elapsed_total * 60.0) if elapsed_total > 0 and inserted else 0.0
        est_10k = (10_000 / rows_per_min * 60.0) if rows_per_min > 0 else None
        est_44k = (44_000 / rows_per_min * 60.0) if rows_per_min > 0 else None
        return {
            **self.to_dict(),
            "elapsed_total_sec": round(elapsed_total, 1),
            "inserted_issues": inserted,
            "rows_per_min": round(rows_per_min, 2),
            "estimated_sec_10k": round(est_10k, 1) if est_10k else None,
            "estimated_sec_44k": round(est_44k, 1) if est_44k else None,
        }


@dataclass
class _SeriesCacheEntry:
    series_id: int
    normalized_name: str
    publisher_norm: str


@dataclass
class WriteGuardState:
    gcd_imported: set[int]
    series_issue_keys: set[tuple[int, str]]
    learned_barcodes: set[str]
    upc_to_issue: dict[str, int]
    series_by_gcd_id: dict[int, _SeriesCacheEntry]
    publisher_id: int
    publisher_norm: str


def load_resume_gcd_issue_ids(session: Session, job_id: int) -> set[int]:
    """GCD issue ids to treat as already written (from a prior job report or catalog rollback ids)."""
    job = session.get(CatalogImportJob, job_id)
    if job is None:
        raise ValueError(f"resume job {job_id} not found")
    cfg = job.config or {}
    report = cfg.get("report") or {}
    rows = report.get("written_rows") or []
    out = {int(r["gcd_issue_id"]) for r in rows if r.get("gcd_issue_id") is not None}
    if out:
        return out
    rollback = cfg.get("rollback") or {}
    issue_ids = [int(x) for x in (rollback.get("issue_ids") or []) if x is not None]
    if not issue_ids:
        return out
    for ext in session.exec(
        select(CatalogIssue.external_source_ids).where(CatalogIssue.id.in_(issue_ids))
    ).all():
        bucket = (ext or {}).get(GCD_SOURCE) or {}
        if isinstance(bucket, dict):
            for key in bucket:
                if str(key).isdigit():
                    out.add(int(key))
    return out


def preload_write_guards(
    session: Session,
    *,
    focus_publisher: str,
    pub_display: str,
    stage_log: Callable[[str], None] | None = None,
    extra_gcd_ids: set[int] | None = None,
) -> WriteGuardState:
    def log(msg: str) -> None:
        if stage_log:
            stage_log(msg)

    t0 = time.perf_counter()
    log("preload: GCD issue ids from catalog...")
    gcd_imported: set[int] = set(extra_gcd_ids or [])
    scanned = 0
    for ext in session.exec(
        select(CatalogIssue.external_source_ids).where(CatalogIssue.external_source_ids.is_not(None))
    ).all():
        scanned += 1
        bucket = (ext or {}).get(GCD_SOURCE) or {}
        if isinstance(bucket, dict):
            for key in bucket:
                if str(key).isdigit():
                    gcd_imported.add(int(key))
    log(f"preload: {scanned:,} external_id rows, {len(gcd_imported):,} GCD issue ids")

    log("preload: series+issue keys...")
    series_issue_keys: set[tuple[int, str]] = set()
    for sid, norm in session.exec(
        select(CatalogIssue.series_id, CatalogIssue.normalized_issue_number)
    ).all():
        if sid is not None and norm:
            series_issue_keys.add((int(sid), str(norm)))
    log(f"preload: {len(series_issue_keys):,} series+issue keys")

    log("preload: barcode guards...")
    learned = {
        str(bc) for bc in session.exec(select(ComicIssueBarcode.normalized_barcode)).all() if bc
    }
    upc_map = {
        str(upc): int(iid)
        for upc, iid in session.exec(select(CatalogUpc.normalized_upc, CatalogUpc.issue_id)).all()
        if upc and iid is not None
    }
    log(f"preload: {len(learned):,} learned, {len(upc_map):,} UPCs")

    log("preload: publisher + GCD series map...")
    pub_row = upsert_publisher(
        session,
        name=pub_display,
        source=GCD_SOURCE,
        external_id=f"publisher:{focus_publisher}",
    )
    publisher_id = int(pub_row.id or 0)
    publisher_norm = pub_row.normalized_name

    series_by_gcd_id: dict[int, _SeriesCacheEntry] = {}
    series_rows = session.exec(
        select(CatalogSeries.id, CatalogSeries.normalized_name, CatalogSeries.external_source_ids)
    ).all()
    for series_id, ser_norm, ext in series_rows:
        if series_id is None:
            continue
        bucket = (ext or {}).get(GCD_SOURCE) or {}
        if isinstance(bucket, dict):
            for key in bucket:
                if str(key).isdigit():
                    series_by_gcd_id[int(key)] = _SeriesCacheEntry(
                        series_id=int(series_id),
                        normalized_name=str(ser_norm),
                        publisher_norm=publisher_norm,
                    )

    session.commit()
    elapsed = time.perf_counter() - t0
    log(f"preload complete ({elapsed:.1f}s)")
    return WriteGuardState(
        gcd_imported=gcd_imported,
        series_issue_keys=series_issue_keys,
        learned_barcodes=learned,
        upc_to_issue=upc_map,
        series_by_gcd_id=series_by_gcd_id,
        publisher_id=publisher_id,
        publisher_norm=publisher_norm,
    )


def _resolve_series(
    session: Session,
    guards: WriteGuardState,
    *,
    gcd_series_id: int,
    series_name: str,
    year: int,
    year_began: int | None,
    timer: WriteBatchTimer,
) -> _SeriesCacheEntry:
    cached = guards.series_by_gcd_id.get(int(gcd_series_id))
    if cached is not None:
        return cached
    t0 = time.perf_counter()
    row = upsert_series(
        session,
        name=str(series_name or "Unknown"),
        publisher_id=guards.publisher_id,
        source=GCD_SOURCE,
        external_id=int(gcd_series_id),
        start_year=year_began if year_began else year,
    )
    entry = _SeriesCacheEntry(
        series_id=int(row.id or 0),
        normalized_name=row.normalized_name,
        publisher_norm=guards.publisher_norm,
    )
    guards.series_by_gcd_id[int(gcd_series_id)] = entry
    timer.publisher_series_sec += time.perf_counter() - t0
    return entry


def _insert_issue_fast(
    session: Session,
    *,
    series_id: int,
    publisher_id: int,
    issue_number: str,
    gcd_issue_id: int,
    cover_date: date | None,
    timer: WriteBatchTimer,
) -> CatalogIssue:
    t0 = time.perf_counter()
    normalized_number = normalize_issue_number(issue_number)
    row = CatalogIssue(
        series_id=series_id,
        publisher_id=publisher_id,
        issue_number=issue_number.strip(),
        normalized_issue_number=normalized_number,
        cover_date=cover_date,
        source_confidence=Decimal("0.95"),
        external_source_ids={"_primary_source": GCD_SOURCE},
    )
    session.add(row)
    session.flush()
    row.external_source_ids = merge_external_ids(row.external_source_ids, GCD_SOURCE, int(gcd_issue_id))
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    timer.issue_insert_sec += time.perf_counter() - t0
    return row


def _insert_variant_fast(session: Session, *, issue_id: int, timer: WriteBatchTimer) -> CatalogVariant:
    t0 = time.perf_counter()
    row = CatalogVariant(
        issue_id=issue_id,
        variant_name="Standard",
        external_source_ids={"_primary_source": GCD_SOURCE},
    )
    session.add(row)
    session.flush()
    timer.variant_insert_sec += time.perf_counter() - t0
    return row


def _insert_upc_memory(
    session: Session,
    guards: WriteGuardState,
    *,
    raw_upc: str,
    issue_id: int,
    variant_id: int | None,
    timer: WriteBatchTimer,
) -> int | None:
    t0 = time.perf_counter()
    upc_id = _insert_upc_if_absent(
        session,
        raw_upc=raw_upc,
        issue_id=issue_id,
        variant_id=variant_id,
        learned=guards.learned_barcodes,
        upc_map=guards.upc_to_issue,
    )
    timer.upc_insert_sec += time.perf_counter() - t0
    return upc_id


def _format_write_error(*, stage: str, row: dict[str, Any], exc: Exception) -> str:
    exc_type = type(exc).__name__
    return (
        f"stage={stage} exc={exc_type} gcd_issue_id={row.get('gcd_issue_id')} "
        f"series={row.get('series')!r} issue_number={row.get('issue_number')!r} "
        f"barcode={row.get('barcode')!r} year={row.get('year')}: {exc}"
    )


def run_p102_gcd_scan_benchmark_dry_run(
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: WriteBatchFilters,
    gcd_imported: set[int] | None = None,
) -> tuple[P102WriteBatchReport, WriteBatchTimer]:
    """Scan/classify only (no Postgres writes). Uses cache matcher + optional GCD id skip set."""
    timer = WriteBatchTimer()
    report = P102WriteBatchReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        filters={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "benchmark_dry_run": True,
        },
    )
    t_pre = time.perf_counter()
    ctx = CatalogCacheContext.load(cache_path)
    timer.preload_sec = time.perf_counter() - t_pre
    skip_gcd = gcd_imported or set()
    seen_gcd_keys: Counter[tuple[str, str, str]] = Counter()
    selected = 0

    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(
        f"""
        SELECT i.id, p.name, s.id, s.name, i.number, i.barcode, i.key_date, s.year_began
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        ORDER BY i.id
        """,
        (filters.year_from, filters.year_to),
    )

    while selected < filters.limit:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for gcd_issue_id, publisher, _gcd_series_id, series, number, barcode, key_date, year_began in batch:
            if selected >= filters.limit:
                break
            timer.gcd_rows_scanned += 1
            t_scan = time.perf_counter()
            year_val = _year_from_key_date(key_date, year_began)
            if year_val is None:
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue
            year = int(year_val)
            focus = canonical_focus_publisher_label(str(publisher or ""))
            if focus != filters.publisher:
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue
            t_skip = time.perf_counter()
            if int(gcd_issue_id) in skip_gcd:
                report.skipped_existing += 1
                timer.skip_checks_sec += time.perf_counter() - t_skip
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue
            if ctx.matcher.matches(
                publisher=str(publisher or focus),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
            ):
                report.skipped_existing += 1
                timer.skip_checks_sec += time.perf_counter() - t_skip
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue
            timer.skip_checks_sec += time.perf_counter() - t_skip
            barcodes = extract_barcodes(barcode)
            cls, _reason, _best_bc, project_issue, project_upc = _classify_missing_row(
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
            timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
            if cls != "clean_primary_candidate" or not project_issue:
                if cls == "duplicate_or_conflict":
                    report.skipped_conflicts += 1
                continue
            report.inserted_issues += 1
            selected += 1
            if project_upc:
                report.inserted_upcs += 1

    conn.close()
    return report, timer


def run_p102_write_batch_fast(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: WriteBatchFilters,
    rollback_collector: dict[str, list[int]] | None = None,
    run_options: WriteBatchRunOptionsFast | None = None,
) -> tuple[P102WriteBatchReport, WriteBatchTimer]:
    opts = run_options or WriteBatchRunOptionsFast()
    stage = lambda msg: _stage(opts, msg)
    timer = WriteBatchTimer()
    report = P102WriteBatchReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        filters={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
            "fast_path": True,
            "commit_batch_size": opts.commit_batch_size,
            "benchmark": opts.benchmark,
            "resume_job_id": opts.resume_job_id,
        },
    )

    t_pre = time.perf_counter()
    stage("loading catalog cache SQLite matcher...")
    ctx = CatalogCacheContext.load(cache_path)
    stage("catalog cache loaded")

    extra_gcd: set[int] = set()
    if opts.resume_job_id is not None:
        extra = load_resume_gcd_issue_ids(session, opts.resume_job_id)
        extra_gcd.update(extra)
        stage(f"resume: skipping {len(extra):,} GCD ids from job {opts.resume_job_id}")

    pub_display = FOCUS_PUBLISHER_NAMES.get(filters.publisher, filters.publisher)
    guards = preload_write_guards(
        session,
        focus_publisher=filters.publisher,
        pub_display=pub_display,
        stage_log=stage,
        extra_gcd_ids=extra_gcd,
    )
    ctx.learned_barcodes = guards.learned_barcodes
    ctx.upc_to_issue = guards.upc_to_issue
    timer.preload_sec = time.perf_counter() - t_pre

    seen_gcd_keys: Counter[tuple[str, str, str]] = Counter()
    selected = 0
    pending_since_commit = 0
    pending_gcd: set[int] = set()
    pending_keys: set[tuple[int, str]] = set()
    pending_matcher_keys: set[tuple[str, str, str]] = set()
    pending_upcs: dict[str, int] = {}

    stage(f"opening GCD SQLite ({gcd_path})...")
    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(
        f"""
        SELECT i.id, p.name, s.id, s.name, i.number, i.barcode, i.key_date, s.year_began
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        ORDER BY i.id
        """,
        (filters.year_from, filters.year_to),
    )
    stage("starting fast write loop (clean_primary_candidate only)...")

    def _revert_pending_guards() -> None:
        for g in pending_gcd:
            guards.gcd_imported.discard(g)
        for k in pending_keys:
            guards.series_issue_keys.discard(k)
        for mk in pending_matcher_keys:
            ctx.matcher.exact_keys.discard(mk)
        for upc, iid in pending_upcs.items():
            guards.upc_to_issue.pop(upc, None)
        pending_gcd.clear()
        pending_keys.clear()
        pending_matcher_keys.clear()
        pending_upcs.clear()

    def _commit_batch() -> None:
        nonlocal pending_since_commit
        if pending_since_commit <= 0:
            return
        t0 = time.perf_counter()
        session.commit()
        timer.commit_sec += time.perf_counter() - t0
        timer.commits += 1
        pending_since_commit = 0
        pending_gcd.clear()
        pending_keys.clear()
        pending_matcher_keys.clear()
        pending_upcs.clear()

    while selected < filters.limit:
        if len(report.errors) > opts.max_errors:
            report.stopped_early = True
            report.stop_reason = f"error_count_exceeded_{opts.max_errors}"
            break
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for gcd_issue_id, publisher, gcd_series_id, series, number, barcode, key_date, year_began in batch:
            if selected >= filters.limit:
                break
            timer.gcd_rows_scanned += 1
            t_scan = time.perf_counter()

            year_val = _year_from_key_date(key_date, year_began)
            if year_val is None:
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue
            year = int(year_val)
            focus = canonical_focus_publisher_label(str(publisher or ""))
            if focus != filters.publisher:
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue

            t_skip = time.perf_counter()
            if int(gcd_issue_id) in guards.gcd_imported:
                report.skipped_existing += 1
                timer.skip_checks_sec += time.perf_counter() - t_skip
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue

            if ctx.matcher.matches(
                publisher=str(publisher or focus),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
            ):
                report.skipped_existing += 1
                timer.skip_checks_sec += time.perf_counter() - t_skip
                timer.gcd_scan_classify_sec += time.perf_counter() - t_scan
                continue
            timer.skip_checks_sec += time.perf_counter() - t_skip

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
            timer.gcd_scan_classify_sec += time.perf_counter() - t_scan

            if cls != "clean_primary_candidate" or not project_issue:
                if cls == "duplicate_or_conflict":
                    report.skipped_conflicts += 1
                continue

            norm_issue = normalize_issue_number(str(number or ""))
            row_ctx = {
                "gcd_issue_id": int(gcd_issue_id),
                "series": series,
                "issue_number": number,
                "barcode": best_bc,
                "year": year,
            }
            try:
                ser = _resolve_series(
                    session,
                    guards,
                    gcd_series_id=int(gcd_series_id),
                    series_name=str(series or ""),
                    year=year,
                    year_began=year_began,
                    timer=timer,
                )
                key = (ser.series_id, norm_issue)
                if key in guards.series_issue_keys:
                    report.skipped_existing += 1
                    continue
                with session.begin_nested():
                    issue_row = _insert_issue_fast(
                        session,
                        series_id=ser.series_id,
                        publisher_id=guards.publisher_id,
                        issue_number=str(number or ""),
                        gcd_issue_id=int(gcd_issue_id),
                        cover_date=_cover_date_from_key_date(key_date, year),
                        timer=timer,
                    )
                    variant_row = _insert_variant_fast(session, issue_id=int(issue_row.id), timer=timer)

                    upc_id: int | None = None
                    inserted_upc = False
                    if project_upc and best_bc:
                        upc_id = _insert_upc_memory(
                            session,
                            guards,
                            raw_upc=best_bc,
                            issue_id=int(issue_row.id),
                            variant_id=int(variant_row.id) if variant_row.id is not None else None,
                            timer=timer,
                        )
                        inserted_upc = upc_id is not None
                        if not inserted_upc:
                            report.skipped_conflicts += 1

                    report.inserted_issues += 1
                    selected += 1
                    pending_since_commit += 1
                    gid = int(gcd_issue_id)
                    guards.gcd_imported.add(gid)
                    pending_gcd.add(gid)
                    guards.series_issue_keys.add(key)
                    pending_keys.add(key)
                    mk = (guards.publisher_norm, ser.normalized_name, norm_issue)
                    ctx.matcher.exact_keys.add(mk)
                    pending_matcher_keys.add(mk)
                    if inserted_upc and best_bc:
                        norm_u = normalize_upc(best_bc)
                        if norm_u:
                            pending_upcs[norm_u] = int(issue_row.id)

                    if rollback_collector is not None:
                        rollback_collector.setdefault("issue_ids", []).append(int(issue_row.id))
                        if variant_row.id is not None:
                            rollback_collector.setdefault("variant_ids", []).append(int(variant_row.id))
                        if upc_id is not None:
                            rollback_collector.setdefault("upc_ids", []).append(upc_id)

                    if inserted_upc:
                        report.inserted_upcs += 1

                    report.written_rows.append(
                        {
                            **row_ctx,
                            "catalog_issue_id": int(issue_row.id),
                            "inserted_upc": inserted_upc,
                        }
                    )

                if pending_since_commit >= opts.commit_batch_size:
                    _commit_batch()

                if opts.log_progress and opts.progress_interval > 0 and selected % opts.progress_interval == 0:
                    print(
                        f"GCD write progress: inserted={report.inserted_issues} upcs={report.inserted_upcs} "
                        f"skipped_existing={report.skipped_existing} skipped_conflicts={report.skipped_conflicts} "
                        f"errors={len(report.errors)} commits={timer.commits}",
                        flush=True,
                    )
            except Exception as exc:
                report.errors.append(
                    _format_write_error(stage="write_row", row=row_ctx, exc=exc)
                )
                if len(report.errors) > opts.max_errors:
                    report.stopped_early = True
                    report.stop_reason = f"error_count_exceeded_{opts.max_errors}"
                    break
        if report.stopped_early:
            break

    _commit_batch()
    conn.close()
    return report, timer


def enrich_report_with_perf(report: P102WriteBatchReport, timer: WriteBatchTimer, elapsed_total: float) -> dict[str, Any]:
    payload = report.to_json()
    payload["perf"] = timer.summary(inserted=report.inserted_issues, elapsed_total=elapsed_total)
    return payload
