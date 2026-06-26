"""P103 controlled enrichment write-batch (update catalog_issue only; max 100 rows)."""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode
from app.services.catalog_ingestion_service import merge_external_ids, normalize_issue_number, normalize_series_name, normalize_upc
from app.services.gcd_catalog_upc_insert_service import insert_catalog_upc_if_absent, preload_catalog_upc_guards
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS, YEAR_EXPR
from app.services.p103_gcd_catalog_enrichment_service import (
    EnrichmentFilters,
    MAX_ENRICHMENT_WRITE_LIMIT,
    _plan_updates_for_pair,
    enrichment_filters_to_dict,
    validate_enrichment_filters,
)
from app.services.p103_gcd_enrichment_fast import (
    _load_catalog_scope,
    load_gcd_index_for_enrichment,
    _lookup_gcd,
    enrichment_cache_ready,
    plan_enrichment_updates,
)
from app.services.p103_gcd_enrichment_helpers import (
    extract_gcd_issue_id,
    gcd_row_to_plan_inputs,
    is_blank,
    resolve_catalog_issue_id_for_gcd_match,
)

logger = logging.getLogger(__name__)


@dataclass
class P103WriteBatchReport:
    mode: str = "enrichment_write_batch"
    report_at: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    updated_issues: int = 0
    inserted_upcs: int = 0
    skipped_no_updates: int = 0
    skipped_conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    written_rows: list[dict[str, Any]] = field(default_factory=list)
    scanned: int = 0
    matched: int = 0
    perf: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        out = {
            "mode": self.mode,
            "report_at": self.report_at,
            "filters": self.filters,
            "updated_issues": self.updated_issues,
            "inserted_upcs": self.inserted_upcs,
            "skipped_no_updates": self.skipped_no_updates,
            "skipped_conflicts": self.skipped_conflicts,
            "errors": self.errors,
            "written_rows": self.written_rows,
            "scanned": self.scanned,
            "matched": self.matched,
        }
        if self.perf is not None:
            out["perf"] = self.perf
        return out


@dataclass
class P103WriteBatchTimer:
    cache_load_sec: float = 0.0
    gcd_index_load_sec: float = 0.0
    match_plan_sec: float = 0.0
    issue_update_sec: float = 0.0
    upc_insert_sec: float = 0.0
    commit_sec: float = 0.0
    rollback_serialize_sec: float = 0.0
    scanned: int = 0
    matched: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_load_sec": round(self.cache_load_sec, 3),
            "gcd_index_load_sec": round(self.gcd_index_load_sec, 3),
            "match_plan_sec": round(self.match_plan_sec, 3),
            "issue_update_sec": round(self.issue_update_sec, 3),
            "upc_insert_sec": round(self.upc_insert_sec, 3),
            "commit_sec": round(self.commit_sec, 3),
            "rollback_serialize_sec": round(self.rollback_serialize_sec, 3),
            "scanned": self.scanned,
            "matched": self.matched,
        }


@dataclass
class _PlannedCatalogWrite:
    issue_id: int
    gcd_issue_id: int
    series_name: str | None
    issue_number: str | None
    planned: list[dict[str, Any]]
    gcd_inputs: dict[str, Any]


def _reload_barcode_guard(session: Session) -> tuple[set[str], dict[str, int], dict[str, int]]:
    learned = {
        str(bc)
        for bc in session.exec(select(ComicIssueBarcode.normalized_barcode)).all()
        if bc
    }
    upc_map, upc_id_by_normalized = preload_catalog_upc_guards(session)
    return learned, upc_map, upc_id_by_normalized


def _date_to_json(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _snapshot_issue(issue: CatalogIssue) -> dict[str, Any]:
    return {
        "external_source_ids": dict(issue.external_source_ids or {}),
        "cover_date": _date_to_json(issue.cover_date),
        "release_date": _date_to_json(issue.release_date),
        "store_date": _date_to_json(issue.store_date),
        "title": issue.title,
        "description": issue.description,
    }


def _snapshot_variant(variant: CatalogVariant | None) -> dict[str, Any] | None:
    if variant is None:
        return None
    return {
        "printing": variant.printing,
        "variant_name": variant.variant_name,
    }


def _apply_planned_updates(
    session: Session,
    issue: CatalogIssue,
    variant: CatalogVariant | None,
    planned: list[dict[str, Any]],
    *,
    learned: set[str],
    upc_map: dict[str, int],
    upc_id_by_normalized: dict[str, int],
) -> tuple[int, int | None, bool]:
    """Return (fields_updated_count, upc_id, upc_row_created)."""
    fields_updated = 0
    upc_id: int | None = None
    upc_created = False
    issue_id = int(issue.id or 0)
    variant_id = int(variant.id) if variant and variant.id is not None else None

    for item in planned:
        field = item.get("field")
        if field == "external_source_ids.gcd_issue":
            issue.external_source_ids = merge_external_ids(
                issue.external_source_ids, GCD_SOURCE, int(item["new"])
            )
            fields_updated += 1
        elif field == "cover_date" and is_blank(issue.cover_date):
            issue.cover_date = date.fromisoformat(str(item["new"]))
            fields_updated += 1
        elif field == "release_date" and is_blank(issue.release_date):
            issue.release_date = date.fromisoformat(str(item["new"]))
            fields_updated += 1
        elif field == "store_date" and is_blank(issue.store_date):
            issue.store_date = date.fromisoformat(str(item["new"]))
            fields_updated += 1
        elif field == "title" and is_blank(issue.title):
            issue.title = str(item["new"])
            fields_updated += 1
        elif field == "description" and is_blank(issue.description):
            issue.description = str(item["new"])
            fields_updated += 1
        elif field == "variant.printing" and variant is not None and is_blank(variant.printing):
            variant.printing = str(item["new"])
            fields_updated += 1
        elif field == "variant.variant_name" and variant is not None and is_blank(variant.variant_name):
            variant.variant_name = str(item["new"])
            fields_updated += 1
        elif field == "catalog_upc" and item.get("action") == "insert":
            upc_id, upc_created = insert_catalog_upc_if_absent(
                session,
                raw_upc=str(item["new"]),
                issue_id=issue_id,
                variant_id=variant_id,
                learned=learned,
                upc_map=upc_map,
                upc_id_by_normalized=upc_id_by_normalized,
            )

    if variant is not None:
        session.add(variant)
    session.add(issue)
    return fields_updated, upc_id, upc_created


BATCH_COMMIT_SIZE = 250
PROGRESS_LOG_EVERY = 250


def _batch_load_issues(session: Session, issue_ids: list[int]) -> dict[int, CatalogIssue]:
    if not issue_ids:
        return {}
    rows = session.exec(select(CatalogIssue).where(CatalogIssue.id.in_(issue_ids))).all()
    return {int(r.id): r for r in rows if r.id is not None}


def _batch_primary_variants(session: Session, issue_ids: list[int]) -> dict[int, CatalogVariant]:
    if not issue_ids:
        return {}
    rows = session.exec(
        select(CatalogVariant)
        .where(CatalogVariant.issue_id.in_(issue_ids))
        .order_by(CatalogVariant.issue_id.asc(), CatalogVariant.id.asc())
    ).all()
    out: dict[int, CatalogVariant] = {}
    for variant in rows:
        iid = int(variant.issue_id)
        if iid not in out:
            out[iid] = variant
    return out


def _filter_planned_for_conflicts(
    planned: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    report: P103WriteBatchReport,
) -> list[dict[str, Any]] | None:
    if any(c.get("reason") in ("learned_barcode_guard", "upc_mapped_elsewhere") for c in conflicts):
        report.skipped_conflicts += 1
        return None
    if conflicts:
        planned = [p for p in planned if p.get("field") != "catalog_upc"]
    if not planned:
        report.skipped_no_updates += 1
        return None
    return planned


def _emit_write_progress(
    *,
    report: P103WriteBatchReport,
    written: int,
    limit: int,
    timer: P103WriteBatchTimer | None,
    verbose: bool,
) -> None:
    if written <= 0 or written % PROGRESS_LOG_EVERY != 0:
        return
    msg = (
        "p103 write progress updated=%s limit=%s scanned=%s matched=%s "
        "inserted_upcs=%s skipped_no_update=%s conflicts=%s errors=%s"
    )
    args = (
        written,
        limit,
        report.scanned,
        report.matched,
        report.inserted_upcs,
        report.skipped_no_updates,
        report.skipped_conflicts,
        len(report.errors),
    )
    logger.info(msg, *args)
    if verbose:
        perf = timer.to_dict() if timer else {}
        print(
            f"P103 write: updated={written}/{limit} scanned={report.scanned} matched={report.matched} "
            f"upcs={report.inserted_upcs} skipped={report.skipped_no_updates} conflicts={report.skipped_conflicts} "
            f"errors={len(report.errors)} perf={perf}",
            flush=True,
        )


def _minimal_written_row(
    *,
    gcd_issue_id: int,
    catalog_issue_id: int,
    fields_updated: int,
    inserted_upc: bool,
    upc_id: int | None,
    barcode: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "gcd_issue_id": int(gcd_issue_id),
        "catalog_issue_id": int(catalog_issue_id),
        "fields_updated": int(fields_updated),
        "inserted_upc": bool(inserted_upc),
        "barcode": barcode,
    }
    if upc_id is not None:
        row["upc_id"] = int(upc_id)
    return row


def _apply_planned_write_batch(
    session: Session,
    *,
    batch: list[_PlannedCatalogWrite],
    learned: set[str],
    upc_map: dict[str, int],
    upc_id_by_normalized: dict[str, int],
    rollback_collector: dict[str, Any] | None,
    report: P103WriteBatchReport,
    timer: P103WriteBatchTimer | None,
) -> tuple[set[str], dict[str, int], dict[str, int]]:
    issue_ids = [p.issue_id for p in batch]
    t_load = time.perf_counter()
    issues = _batch_load_issues(session, issue_ids)
    variants = _batch_primary_variants(session, issue_ids)
    if timer:
        timer.issue_update_sec += time.perf_counter() - t_load

    pending_rollbacks: list[dict[str, Any]] = []
    pending_upc_ids: list[int] = []
    pending_written: list[dict[str, Any]] = []
    batch_updated = 0

    t_apply = time.perf_counter()
    for planned_write in batch:
        issue = issues.get(planned_write.issue_id)
        if issue is None:
            report.errors.append(f"catalog_issue_id={planned_write.issue_id}: missing issue row")
            continue
        variant = variants.get(planned_write.issue_id)
        before_issue = _snapshot_issue(issue)
        before_variant = _snapshot_variant(variant)
        t_row = time.perf_counter()
        fields_updated, upc_id, upc_created = _apply_planned_updates(
            session,
            issue,
            variant,
            planned_write.planned,
            learned=learned,
            upc_map=upc_map,
            upc_id_by_normalized=upc_id_by_normalized,
        )
        row_sec = time.perf_counter() - t_row
        if timer:
            if any(p.get("field") == "catalog_upc" for p in planned_write.planned):
                timer.upc_insert_sec += row_sec
            else:
                timer.issue_update_sec += row_sec

        if fields_updated == 0 and upc_id is None:
            report.skipped_no_updates += 1
            continue

        batch_updated += 1
        if upc_created:
            report.inserted_upcs += 1

        pending_rollbacks.append(
            {
                "catalog_issue_id": planned_write.issue_id,
                "catalog_variant_id": int(variant.id) if variant and variant.id else None,
                "before": before_issue,
                "variant_before": before_variant,
            }
        )
        if upc_created and upc_id is not None:
            pending_upc_ids.append(upc_id)

        pending_written.append(
            _minimal_written_row(
                gcd_issue_id=planned_write.gcd_issue_id,
                catalog_issue_id=planned_write.issue_id,
                fields_updated=fields_updated,
                inserted_upc=upc_created,
                upc_id=upc_id,
                barcode=planned_write.gcd_inputs.get("barcode"),
            )
        )

    if timer:
        timer.issue_update_sec += time.perf_counter() - t_apply

    if batch_updated == 0:
        session.rollback()
        return learned, upc_map, upc_id_by_normalized

    t_commit = time.perf_counter()
    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        report.errors.append(f"batch commit failed ({batch_updated} rows): {exc}")
        learned, upc_map, upc_id_by_normalized = _reload_barcode_guard(session)
        return learned, upc_map, upc_id_by_normalized
    if timer:
        timer.commit_sec += time.perf_counter() - t_commit

    report.updated_issues += batch_updated
    if rollback_collector is not None:
        rollback_collector.setdefault("issue_snapshots", []).extend(pending_rollbacks)
        if pending_upc_ids:
            rollback_collector.setdefault("upc_ids", []).extend(pending_upc_ids)
    report.written_rows.extend(pending_written)

    return learned, upc_map, upc_id_by_normalized


def _commit_enrichment_row(
    session: Session,
    *,
    issue: CatalogIssue,
    variant: CatalogVariant | None,
    planned: list[dict[str, Any]],
    gcd_issue_id: int,
    series_name: str | None,
    number: str | None,
    gcd_inputs: dict[str, Any],
    learned: set[str],
    upc_map: dict[str, int],
    rollback_collector: dict[str, Any] | None,
    report: P103WriteBatchReport,
    upc_id_by_normalized: dict[str, int],
) -> tuple[bool, set[str], dict[str, int], dict[str, int]]:
    """Apply planned updates; return (written_ok, learned, upc_map)."""
    try:
        before_issue = _snapshot_issue(issue)
        before_variant = _snapshot_variant(variant)
        fields_updated, upc_id, upc_created = _apply_planned_updates(
            session,
            issue,
            variant,
            planned,
            learned=learned,
            upc_map=upc_map,
            upc_id_by_normalized=upc_id_by_normalized,
        )
        if fields_updated == 0 and upc_id is None:
            report.skipped_no_updates += 1
            session.rollback()
            return False, learned, upc_map, upc_id_by_normalized

        session.commit()
        report.updated_issues += 1
        if upc_created:
            report.inserted_upcs += 1

        issue_id = int(issue.id or 0)
        if rollback_collector is not None:
            rollback_collector.setdefault("issue_snapshots", []).append(
                {
                    "catalog_issue_id": issue_id,
                    "catalog_variant_id": int(variant.id) if variant and variant.id else None,
                    "before": before_issue,
                    "variant_before": before_variant,
                }
            )
            if upc_created and upc_id is not None:
                rollback_collector.setdefault("upc_ids", []).append(upc_id)

        report.written_rows.append(
            _minimal_written_row(
                gcd_issue_id=int(gcd_issue_id),
                catalog_issue_id=issue_id,
                fields_updated=fields_updated,
                inserted_upc=upc_created,
                upc_id=upc_id,
                barcode=gcd_inputs.get("barcode"),
            )
        )
        return True, learned, upc_map, upc_id_by_normalized
    except Exception as exc:
        session.rollback()
        report.errors.append(f"catalog_issue_id={issue.id}: {exc}")
        learned, upc_map, upc_id_by_normalized = _reload_barcode_guard(session)
        return False, learned, upc_map, upc_id_by_normalized


def _run_p103_enrichment_write_batch_all_catalog(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    report: P103WriteBatchReport,
    ctx: CatalogCacheContext,
    learned: set[str],
    upc_map: dict[str, int],
    rollback_collector: dict[str, Any] | None,
    timer: P103WriteBatchTimer | None = None,
    verbose_progress: bool = False,
    upc_id_by_normalized: dict[str, int],
) -> P103WriteBatchReport:
    if not enrichment_cache_ready(cache_path):
        raise ValueError("--all requires catalog_enrichment_issue cache; run with --refresh-cache.")

    t0 = time.perf_counter()
    catalog_scope = _load_catalog_scope(cache_path, filters=filters)
    if timer:
        timer.cache_load_sec += time.perf_counter() - t0

    t_gcd = time.perf_counter()
    index_cache_dir = gcd_path.parent / "p103_gcd_index_cache"
    gcd_index = load_gcd_index_for_enrichment(
        gcd_path,
        year_from=filters.year_from,
        year_to=filters.year_to,
        focus_publisher=filters.publisher,
        all_catalog=True,
        year_filter_explicit=filters.year_filter_explicit,
        catalog_scope=catalog_scope,
        index_cache_dir=index_cache_dir,
    )
    if timer:
        timer.gcd_index_load_sec = time.perf_counter() - t_gcd

    limit = int(filters.limit or 0)
    seen_issues: set[int] = set()
    pending: list[_PlannedCatalogWrite] = []
    written = 0

    t_match = time.perf_counter()
    for snap in catalog_scope:
        report.scanned += 1
        if timer:
            timer.scanned += 1
        if written >= limit:
            break
        if snap.issue_id in seen_issues:
            continue

        gcd_row = _lookup_gcd(gcd_index, snap)
        if gcd_row is None:
            continue

        report.matched += 1
        if timer:
            timer.matched += 1

        gcd_inputs = gcd_row_to_plan_inputs(gcd_row)
        planned, conflicts, _ = plan_enrichment_updates(snap, gcd_inputs, ctx=ctx)
        planned = _filter_planned_for_conflicts(planned, conflicts, report)
        if planned is None:
            seen_issues.add(snap.issue_id)
            continue

        seen_issues.add(snap.issue_id)
        pending.append(
            _PlannedCatalogWrite(
                issue_id=snap.issue_id,
                gcd_issue_id=int(gcd_row["issue_id"]),
                series_name=snap.series_name,
                issue_number=snap.issue_number,
                planned=planned,
                gcd_inputs=gcd_inputs,
            )
        )
        written += 1

    if timer:
        timer.match_plan_sec = time.perf_counter() - t_match

    for offset in range(0, len(pending), BATCH_COMMIT_SIZE):
        chunk = pending[offset : offset + BATCH_COMMIT_SIZE]
        learned, upc_map, upc_id_by_normalized = _apply_planned_write_batch(
            session,
            batch=chunk,
            learned=learned,
            upc_map=upc_map,
            upc_id_by_normalized=upc_id_by_normalized,
            rollback_collector=rollback_collector,
            report=report,
            timer=timer,
        )
        ctx.learned_barcodes = learned
        ctx.upc_to_issue = upc_map
        _emit_write_progress(
            report=report,
            written=report.updated_issues,
            limit=limit,
            timer=timer,
            verbose=verbose_progress,
        )

    return report


def run_p103_enrichment_write_batch(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    rollback_collector: dict[str, Any] | None = None,
    benchmark_write_limit: int | None = None,
    verbose_progress: bool = False,
) -> P103WriteBatchReport:
    effective_limit = int(filters.limit or 0)
    if benchmark_write_limit is not None:
        effective_limit = min(effective_limit, int(benchmark_write_limit))
        verbose_progress = True
    if effective_limit <= 0:
        raise ValueError("P103 write limit must be positive")

    filters = EnrichmentFilters(
        publisher=filters.publisher,
        year_from=filters.year_from,
        year_to=filters.year_to,
        limit=effective_limit,
        all_catalog=filters.all_catalog,
        year_filter_explicit=filters.year_filter_explicit,
    )

    if filters.limit is None or filters.limit > MAX_ENRICHMENT_WRITE_LIMIT:
        raise ValueError(f"P103 write limit must be 1–{MAX_ENRICHMENT_WRITE_LIMIT}")

    timer = P103WriteBatchTimer() if verbose_progress or benchmark_write_limit is not None else None

    report = P103WriteBatchReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        filters=enrichment_filters_to_dict(filters),
    )

    t_ctx = time.perf_counter()
    ctx = CatalogCacheContext.load(cache_path)
    if timer:
        timer.cache_load_sec = time.perf_counter() - t_ctx
    learned, upc_map, upc_id_by_normalized = _reload_barcode_guard(session)
    ctx.learned_barcodes = learned
    ctx.upc_to_issue = upc_map

    if filters.all_catalog:
        report = _run_p103_enrichment_write_batch_all_catalog(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            report=report,
            ctx=ctx,
            learned=learned,
            upc_map=upc_map,
            rollback_collector=rollback_collector,
            timer=timer,
            verbose_progress=verbose_progress,
            upc_id_by_normalized=upc_id_by_normalized,
        )
        report.scanned = timer.scanned if timer else report.scanned
        report.matched = timer.matched if timer else report.matched
        if timer:
            report.perf = timer.to_dict()
        return report

    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(
        f"""
        SELECT i.id AS issue_id, p.id AS gcd_publisher_id, p.name AS publisher_name,
               s.id AS gcd_series_id, s.name AS series_name,
               i.number, i.barcode, i.key_date, s.year_began,
               i.title AS title, i.notes AS notes
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        ORDER BY i.id
        """,
        (filters.year_from, filters.year_to),
    )

    seen_issues: set[int] = set()
    written = 0

    while written < filters.limit:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for row in batch:
            if written >= filters.limit:
                break
            (
                gcd_issue_id,
                gcd_publisher_id,
                publisher_name,
                gcd_series_id,
                series_name,
                number,
                barcode,
                key_date,
                year_began,
                title,
                notes,
            ) = row
            focus = canonical_focus_publisher_label(str(publisher_name or ""))
            if focus is None or focus != filters.publisher:
                continue
            if not ctx.matcher.matches(
                publisher=str(publisher_name or focus),
                series=str(series_name or ""),
                issue_number=str(number or ""),
                year=None,
            ):
                continue

            issue_id = resolve_catalog_issue_id_for_gcd_match(
                cache_path,
                publisher=str(publisher_name or focus),
                series=str(series_name or ""),
                issue_number=str(number or ""),
            )
            if issue_id is None or issue_id in seen_issues:
                continue

            issue = session.get(CatalogIssue, issue_id)
            if issue is None:
                continue

            gcd_inputs = gcd_row_to_plan_inputs(
                {
                    "issue_id": gcd_issue_id,
                    "gcd_publisher_id": gcd_publisher_id,
                    "gcd_series_id": gcd_series_id,
                    "publisher_name": publisher_name,
                    "series_name": series_name,
                    "number": number,
                    "barcode": barcode,
                    "key_date": key_date,
                    "year_began": year_began,
                    "title": title,
                    "notes": notes,
                }
            )

            variant = session.exec(
                select(CatalogVariant).where(CatalogVariant.issue_id == issue_id).order_by(CatalogVariant.id.asc())
            ).first()

            planned, conflicts, _ = _plan_updates_for_pair(session, issue, gcd_inputs, ctx=ctx)
            if any(c.get("reason") in ("learned_barcode_guard", "upc_mapped_elsewhere") for c in conflicts):
                report.skipped_conflicts += 1
                continue
            if conflicts:
                planned = [p for p in planned if p.get("field") != "catalog_upc"]
            if not planned:
                report.skipped_no_updates += 1
                seen_issues.add(issue_id)
                continue

            try:
                before_issue = _snapshot_issue(issue)
                before_variant = _snapshot_variant(variant)
                fields_updated, upc_id, upc_created = _apply_planned_updates(
                    session,
                    issue,
                    variant,
                    planned,
                    learned=learned,
                    upc_map=upc_map,
                    upc_id_by_normalized=upc_id_by_normalized,
                )
                if fields_updated == 0 and upc_id is None:
                    report.skipped_no_updates += 1
                    session.rollback()
                    continue

                session.commit()
                seen_issues.add(issue_id)
                written += 1
                _emit_write_progress(
                    report=report,
                    written=written,
                    limit=int(filters.limit or 0),
                    timer=None,
                    verbose=verbose_progress,
                )
                report.updated_issues += 1
                if upc_created:
                    report.inserted_upcs += 1

                if rollback_collector is not None:
                    rollback_collector.setdefault("issue_snapshots", []).append(
                        {
                            "catalog_issue_id": issue_id,
                            "catalog_variant_id": int(variant.id) if variant and variant.id else None,
                            "before": before_issue,
                            "variant_before": before_variant,
                        }
                    )
                    if upc_created and upc_id is not None:
                        rollback_collector.setdefault("upc_ids", []).append(upc_id)

                report.written_rows.append(
                    _minimal_written_row(
                        gcd_issue_id=int(gcd_issue_id),
                        catalog_issue_id=issue_id,
                        fields_updated=fields_updated,
                        inserted_upc=upc_created,
                        upc_id=upc_id,
                        barcode=gcd_inputs.get("barcode"),
                    )
                )
            except Exception as exc:
                session.rollback()
                report.errors.append(f"catalog_issue_id={issue_id}: {exc}")
                learned, upc_map, upc_id_by_normalized = _reload_barcode_guard(session)
                ctx.learned_barcodes = learned
                ctx.upc_to_issue = upc_map

    conn.close()
    return report
