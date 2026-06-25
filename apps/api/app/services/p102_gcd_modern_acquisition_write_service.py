"""P102 controlled write-batch (catalog_issue + catalog_upc from GCD)."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.models.intake_queue import ComicIssueBarcode
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_upc,
    upsert_issue,
    upsert_publisher,
    upsert_series,
    upsert_variant,
)
from app.services.gcd_barcode_import_service import GCD_SOURCE, _year_from_key_date, extract_barcodes
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import (
    FOCUS_PUBLISHERS,
    YEAR_EXPR,
    _classify_missing_row,
)

MAX_WRITE_BATCH_LIMIT = 100
MAX_LARGE_WRITE_BATCH_LIMIT = 10_000

logger = logging.getLogger(__name__)

FOCUS_PUBLISHER_NAMES: dict[str, str] = {
    "Marvel": "Marvel",
    "DC": "DC Comics",
    "Image": "Image",
    "Boom": "BOOM! Studios",
    "IDW": "IDW Publishing",
    "Dark Horse": "Dark Horse Comics",
    "Dynamite": "Dynamite Entertainment",
    "Valiant": "Valiant Entertainment",
}


@dataclass
class WriteBatchFilters:
    publisher: str
    year_from: int
    year_to: int
    limit: int


@dataclass
class WriteBatchRunOptions:
    progress_interval: int = 250
    max_errors: int = 25
    log_progress: bool = True
    stage_log: Callable[[str], None] | None = None


def _stage(opts: WriteBatchRunOptions, message: str) -> None:
    if opts.stage_log is not None:
        opts.stage_log(message)
    else:
        print(message, flush=True)


@dataclass
class P102WriteBatchReport:
    mode: str = "write_batch"
    report_at: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    inserted_issues: int = 0
    inserted_upcs: int = 0
    skipped_existing: int = 0
    skipped_conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    written_rows: list[dict[str, Any]] = field(default_factory=list)
    stopped_early: bool = False
    stop_reason: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "report_at": self.report_at,
            "filters": self.filters,
            "inserted_issues": self.inserted_issues,
            "inserted_upcs": self.inserted_upcs,
            "skipped_existing": self.skipped_existing,
            "skipped_conflicts": self.skipped_conflicts,
            "errors": self.errors,
            "written_rows": self.written_rows,
            "stopped_early": self.stopped_early,
            "stop_reason": self.stop_reason,
        }


def validate_write_batch_args(
    *,
    write_batch: bool,
    limit: int | None,
    publisher: str | None,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
    confirm_write: str | None,
    large_batch: bool = False,
) -> WriteBatchFilters | None:
    if not write_batch:
        return None
    missing: list[str] = []
    cap = MAX_LARGE_WRITE_BATCH_LIMIT if large_batch else MAX_WRITE_BATCH_LIMIT
    if limit is None or limit <= 0:
        missing.append("--limit (positive integer)")
    elif int(limit) > cap:
        raise ValueError(f"--limit must be at most {cap} for this write mode.")
    if not publisher:
        missing.append("--publisher")
    elif publisher not in FOCUS_PUBLISHERS:
        raise ValueError(f"--publisher must be one of: {', '.join(FOCUS_PUBLISHERS)}")
    has_year = year is not None
    has_range = year_from is not None or year_to is not None
    if has_year and has_range:
        raise ValueError("Use either --year or --year-from/--year-to, not both.")
    if not has_year and not has_range:
        missing.append("--year or --year-from/--year-to")
    if confirm_write != "YES":
        missing.append('--confirm-write YES')
    if missing:
        raise ValueError(" --write-batch requires: " + ", ".join(missing))
    if has_year:
        yf = yt = int(year)
    else:
        yf = int(year_from if year_from is not None else year_to)
        yt = int(year_to if year_to is not None else year_from)
    if yf > yt:
        yf, yt = yt, yf
    return WriteBatchFilters(publisher=publisher, year_from=yf, year_to=yt, limit=int(limit))


def _cover_date_from_key_date(key_date: str | None, year: int) -> date:
    text = str(key_date or "").strip()
    if len(text) >= 7 and text[4] == "-":
        try:
            y = int(text[0:4])
            m = int(text[5:7])
            d = int(text[8:10]) if len(text) >= 10 and text[8:10].isdigit() else 1
            if m == 0:
                m = 1
            if d == 0:
                d = 1
            return date(y, m, d)
        except (TypeError, ValueError):
            pass
    return date(year, 1, 1)


def _gcd_issue_ids_in_catalog(session: Session, *, stage_log: Callable[[str], None] | None = None) -> set[int]:
    def log(msg: str) -> None:
        if stage_log:
            stage_log(msg)

    log("scanning catalog for existing GCD issue links (external_source_ids only)...")
    out: set[int] = set()
    scanned = 0
    stmt = select(CatalogIssue.external_source_ids).where(CatalogIssue.external_source_ids.is_not(None))
    for ext in session.exec(stmt).all():
        scanned += 1
        if scanned % 50_000 == 0:
            log(f"  GCD id scan progress: {scanned:,} rows...")
        bucket = (ext or {}).get(GCD_SOURCE) or {}
        if isinstance(bucket, dict):
            for key in bucket:
                if str(key).isdigit():
                    out.add(int(key))
    log(f"  GCD id scan done: {scanned:,} rows, {len(out):,} GCD issue ids")
    return out


def _reload_barcode_guard(
    session: Session, *, stage_log: Callable[[str], None] | None = None
) -> tuple[set[str], dict[str, int]]:
    if stage_log:
        stage_log("loading barcode guards (learned + catalog_upc)...")
    learned = {
        str(bc)
        for bc in session.exec(select(ComicIssueBarcode.normalized_barcode)).all()
        if bc
    }
    upc_map = {
        str(upc): int(iid)
        for upc, iid in session.exec(select(CatalogUpc.normalized_upc, CatalogUpc.issue_id)).all()
        if upc and iid is not None
    }
    if stage_log:
        stage_log(f"  barcode guards: {len(learned):,} learned, {len(upc_map):,} catalog UPCs")
    return learned, upc_map


def _insert_upc_if_absent(
    session: Session,
    *,
    raw_upc: str,
    issue_id: int,
    variant_id: int | None,
    learned: set[str],
    upc_map: dict[str, int],
) -> int | None:
    normalized = normalize_upc(raw_upc)
    if not normalized:
        return None
    if normalized in learned:
        return None
    if normalized in upc_map:
        return None
    if session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first() is not None:
        return None
    row = CatalogUpc(
        upc=raw_upc.strip(),
        normalized_upc=normalized,
        issue_id=issue_id,
        variant_id=variant_id,
        source=GCD_SOURCE,
        confidence=Decimal("1.0"),
        barcode_type="upc",
    )
    session.add(row)
    session.flush()
    upc_map[normalized] = issue_id
    return int(row.id) if row.id is not None else None


def run_p102_write_batch(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: WriteBatchFilters,
    rollback_collector: dict[str, list[int]] | None = None,
    run_options: WriteBatchRunOptions | None = None,
) -> P102WriteBatchReport:
    """Insert up to ``limit`` clean_primary_candidate rows matching publisher/year filters."""
    opts = run_options or WriteBatchRunOptions()
    stage = lambda msg: _stage(opts, msg)
    report = P102WriteBatchReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        filters={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
        },
    )
    stage("loading catalog cache SQLite matcher...")
    ctx = CatalogCacheContext.load(cache_path)
    stage("catalog cache loaded")
    gcd_imported = _gcd_issue_ids_in_catalog(session, stage_log=stage)
    learned, upc_map = _reload_barcode_guard(session, stage_log=stage)
    ctx.learned_barcodes = learned
    ctx.upc_to_issue = upc_map

    from collections import Counter

    seen_gcd_keys: Counter[tuple[str, str, str]] = Counter()
    selected = 0

    stage(f"opening GCD SQLite ({gcd_path})...")
    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    stage(f"scanning GCD candidates {filters.year_from}-{filters.year_to} for {filters.publisher}...")
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

    pub_display = FOCUS_PUBLISHER_NAMES.get(filters.publisher, filters.publisher)
    stage("starting write loop (clean_primary_candidate only)...")

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
            year_val = _year_from_key_date(key_date, year_began)
            if year_val is None:
                continue
            year = int(year_val)
            focus = canonical_focus_publisher_label(str(publisher or ""))
            if focus != filters.publisher:
                continue

            if int(gcd_issue_id) in gcd_imported:
                report.skipped_existing += 1
                continue

            if ctx.matcher.matches(
                publisher=str(publisher or focus),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
            ):
                report.skipped_existing += 1
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
            if cls != "clean_primary_candidate" or not project_issue:
                if cls == "duplicate_or_conflict":
                    report.skipped_conflicts += 1
                continue

            try:
                pub_row = upsert_publisher(
                    session,
                    name=pub_display,
                    source=GCD_SOURCE,
                    external_id=f"publisher:{publisher}",
                )
                series_row = upsert_series(
                    session,
                    name=str(series or "Unknown"),
                    publisher_id=int(pub_row.id) if pub_row.id is not None else None,
                    source=GCD_SOURCE,
                    external_id=int(gcd_series_id),
                    start_year=year_began if year_began else year,
                )
                norm_issue = normalize_issue_number(str(number or ""))
                if session.exec(
                    select(CatalogIssue)
                    .where(CatalogIssue.series_id == int(series_row.id))
                    .where(CatalogIssue.normalized_issue_number == norm_issue)
                ).first():
                    report.skipped_existing += 1
                    continue
                issue_row = upsert_issue(
                    session,
                    series_id=int(series_row.id),
                    publisher_id=int(pub_row.id) if pub_row.id is not None else None,
                    issue_number=str(number or ""),
                    source=GCD_SOURCE,
                    external_id=int(gcd_issue_id),
                    cover_date=_cover_date_from_key_date(key_date, year),
                    source_confidence=Decimal("0.95"),
                )
                variant_row = upsert_variant(session, issue_id=int(issue_row.id), source=GCD_SOURCE)
                report.inserted_issues += 1
                selected += 1
                gcd_imported.add(int(gcd_issue_id))

                ctx.matcher.exact_keys.add(
                    (
                        pub_row.normalized_name,
                        series_row.normalized_name,
                        issue_row.normalized_issue_number,
                    )
                )

                inserted_upc = False
                upc_id: int | None = None
                if project_upc and best_bc:
                    upc_id = _insert_upc_if_absent(
                        session,
                        raw_upc=best_bc,
                        issue_id=int(issue_row.id),
                        variant_id=int(variant_row.id) if variant_row.id is not None else None,
                        learned=learned,
                        upc_map=upc_map,
                    )
                    inserted_upc = upc_id is not None
                    if inserted_upc:
                        report.inserted_upcs += 1
                    else:
                        report.skipped_conflicts += 1

                session.commit()
                if rollback_collector is not None:
                    rollback_collector.setdefault("issue_ids", []).append(int(issue_row.id))
                    if variant_row.id is not None:
                        rollback_collector.setdefault("variant_ids", []).append(int(variant_row.id))
                    if upc_id is not None:
                        rollback_collector.setdefault("upc_ids", []).append(upc_id)
                report.written_rows.append(
                    {
                        "gcd_issue_id": int(gcd_issue_id),
                        "catalog_issue_id": int(issue_row.id),
                        "series": series,
                        "issue_number": number,
                        "year": year,
                        "barcode": best_bc,
                        "inserted_upc": inserted_upc,
                    }
                )
                if opts.log_progress and opts.progress_interval > 0 and selected % opts.progress_interval == 0:
                    msg = (
                        f"GCD write progress: inserted={report.inserted_issues} upcs={report.inserted_upcs} "
                        f"skipped_existing={report.skipped_existing} skipped_conflicts={report.skipped_conflicts} "
                        f"errors={len(report.errors)}"
                    )
                    logger.info(msg)
                    print(msg, flush=True)
            except Exception as exc:
                session.rollback()
                report.errors.append(f"gcd_issue_id={gcd_issue_id}: {exc}")
                learned, upc_map = _reload_barcode_guard(session, stage_log=stage)
                ctx.learned_barcodes = learned
                ctx.upc_to_issue = upc_map
                if len(report.errors) > opts.max_errors:
                    report.stopped_early = True
                    report.stop_reason = f"error_count_exceeded_{opts.max_errors}"
                    break
        if report.stopped_early:
            break

    conn.close()
    return report
