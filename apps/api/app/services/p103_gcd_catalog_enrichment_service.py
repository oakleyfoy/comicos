"""P103 — GCD catalog enrichment dry-run (update existing catalog_issue only)."""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.services.p101_catalog_cache_service import CatalogCacheContext, YEAR_MAX, YEAR_MIN
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS, YEAR_EXPR
from app.services.catalog_ingestion_service import normalize_series_name, normalize_upc
from app.services.p103_gcd_enrichment_helpers import (
    extract_gcd_issue_id,
    gcd_row_to_plan_inputs,
    is_blank,
    resolve_catalog_issue_id_for_gcd_match,
)

P103_JOB_SOURCE = "GCD"
P103_JOB_TYPE_DRY_RUN = "gcd_enrichment_dry_run"
P103_JOB_TYPE_WRITE = "gcd_enrichment_write_batch"

MAX_ENRICHMENT_WRITE_LIMIT = 50_000


@dataclass
class EnrichmentFilters:
    publisher: str | None
    year_from: int
    year_to: int
    limit: int | None = None
    all_catalog: bool = False
    year_filter_explicit: bool = False


@dataclass
class P103DryRunReport:
    report_at: str = ""
    mode: str = "dry_run"
    gcd_database: str = ""
    catalog_cache: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    catalog_issues_in_scope: int = 0
    matched_to_gcd: int = 0
    missing_gcd_ids: int = 0
    missing_upc: int = 0
    missing_dates: int = 0
    missing_printing: int = 0
    missing_variants: int = 0
    missing_titles: int = 0
    missing_notes: int = 0
    projected_field_updates: int = 0
    projected_upc_inserts: int = 0
    conflicts: int = 0
    skipped_no_catalog_match: int = 0
    updates_by_field: dict[str, int] = field(default_factory=dict)
    conflict_samples: list[dict[str, Any]] = field(default_factory=list)
    sample_updates: list[dict[str, Any]] = field(default_factory=list)
    perf: dict[str, Any] | None = None
    notes: tuple[str, ...] = field(
        default=(
            "Update-only: no catalog_issue inserts.",
            "Never overwrite existing UPCs or learned barcodes.",
            "Dates/titles filled only when ComicOS value is blank.",
            "Publisher/series/issue number changes are conflicts only (not applied).",
        )
    )

    def to_json(self) -> dict[str, Any]:
        return {
            "report_at": self.report_at,
            "mode": self.mode,
            "gcd_database": self.gcd_database,
            "catalog_cache": self.catalog_cache,
            "filters": self.filters,
            "elapsed_seconds": self.elapsed_seconds,
            "catalog_issues_in_scope": self.catalog_issues_in_scope,
            "matched_to_gcd": self.matched_to_gcd,
            "missing_gcd_ids": self.missing_gcd_ids,
            "missing_upc": self.missing_upc,
            "missing_dates": self.missing_dates,
            "missing_printing": self.missing_printing,
            "missing_variants": self.missing_variants,
            "missing_titles": self.missing_titles,
            "missing_notes": self.missing_notes,
            "projected_field_updates": self.projected_field_updates,
            "projected_upc_inserts": self.projected_upc_inserts,
            "conflicts": self.conflicts,
            "skipped_no_catalog_match": self.skipped_no_catalog_match,
            "updates_by_field": dict(self.updates_by_field),
            "conflict_samples": self.conflict_samples,
            "sample_updates": self.sample_updates,
            "notes": list(self.notes),
            "perf": self.perf,
        }


def validate_enrichment_filters(
    *,
    write_batch: bool,
    limit: int | None,
    publisher: str | None,
    year: int | None,
    year_from: int | None,
    year_to: int | None,
    confirm_write: str | None,
    all_catalog: bool = False,
) -> EnrichmentFilters | None:
    has_year = year is not None
    has_range = year_from is not None or year_to is not None
    if has_year and has_range:
        raise ValueError("Use either --year or --year-from/--year-to, not both.")

    if all_catalog:
        if write_batch:
            missing: list[str] = []
            if limit is None or limit <= 0:
                missing.append("--limit (positive integer)")
            elif int(limit) > MAX_ENRICHMENT_WRITE_LIMIT:
                raise ValueError(f"P103 write limit must be at most {MAX_ENRICHMENT_WRITE_LIMIT}.")
            if confirm_write != "YES":
                missing.append("--confirm-write YES")
            if missing:
                raise ValueError(" --write-batch requires: " + ", ".join(missing))
        elif limit is not None and limit <= 0:
            raise ValueError("--limit must be positive when provided.")

        year_filter_explicit = has_year or has_range
        if year_filter_explicit:
            if has_year:
                yf = yt = int(year)
            else:
                yf = int(year_from if year_from is not None else year_to)
                yt = int(year_to if year_to is not None else year_from)
            if yf > yt:
                yf, yt = yt, yf
        else:
            yf, yt = YEAR_MIN, YEAR_MAX

        if publisher is not None and publisher.strip():
            pass  # ignored in whole-catalog mode

        return EnrichmentFilters(
            publisher=None,
            year_from=yf,
            year_to=yt,
            limit=limit,
            all_catalog=True,
            year_filter_explicit=year_filter_explicit,
        )

    if not write_batch:
        if limit is not None and limit <= 0:
            raise ValueError("--limit must be positive when provided.")
        if not publisher:
            raise ValueError("--publisher is required (or use --all for whole-catalog mode).")
        if publisher not in FOCUS_PUBLISHERS:
            raise ValueError(f"--publisher must be one of: {', '.join(FOCUS_PUBLISHERS)}")
        if not has_year and not has_range:
            raise ValueError("--year or --year-from/--year-to required for scoped dry-run.")
        if has_year:
            yf = yt = int(year)
        else:
            yf = int(year_from if year_from is not None else year_to)
            yt = int(year_to if year_to is not None else year_from)
        if yf > yt:
            yf, yt = yt, yf
        return EnrichmentFilters(
            publisher=publisher,
            year_from=yf,
            year_to=yt,
            limit=limit,
            all_catalog=False,
            year_filter_explicit=True,
        )

    missing = []
    if limit is None or limit <= 0:
        missing.append("--limit (positive integer)")
    elif int(limit) > MAX_ENRICHMENT_WRITE_LIMIT:
        raise ValueError(f"P103 write limit must be at most {MAX_ENRICHMENT_WRITE_LIMIT}.")
    if not publisher:
        missing.append("--publisher (or use --all)")
    elif publisher not in FOCUS_PUBLISHERS:
        raise ValueError(f"--publisher must be one of: {', '.join(FOCUS_PUBLISHERS)}")
    if not has_year and not has_range:
        missing.append("--year or --year-from/--year-to")
    if confirm_write != "YES":
        missing.append("--confirm-write YES")
    if missing:
        raise ValueError(" --write-batch requires: " + ", ".join(missing))
    if has_year:
        yf = yt = int(year)
    else:
        yf = int(year_from if year_from is not None else year_to)
        yt = int(year_to if year_to is not None else year_from)
    if yf > yt:
        yf, yt = yt, yf
    return EnrichmentFilters(
        publisher=publisher,
        year_from=yf,
        year_to=yt,
        limit=int(limit),
        all_catalog=False,
        year_filter_explicit=True,
    )


def enrichment_filters_to_dict(filters: EnrichmentFilters) -> dict[str, Any]:
    return {
        "all_catalog": filters.all_catalog,
        "publisher": filters.publisher,
        "year_from": filters.year_from,
        "year_to": filters.year_to,
        "year_filter_explicit": filters.year_filter_explicit,
        "limit": filters.limit,
    }


def _load_issues(session: Session, issue_ids: list[int]) -> dict[int, CatalogIssue]:
    if not issue_ids:
        return {}
    rows = session.exec(select(CatalogIssue).where(CatalogIssue.id.in_(issue_ids))).all()
    return {int(r.id): r for r in rows if r.id is not None}


def _issue_has_upc(session: Session, issue_id: int) -> bool:
    row = session.exec(select(CatalogUpc.id).where(CatalogUpc.issue_id == issue_id).limit(1)).first()
    return row is not None


def _primary_variant(session: Session, issue_id: int) -> CatalogVariant | None:
    return session.exec(
        select(CatalogVariant).where(CatalogVariant.issue_id == issue_id).order_by(CatalogVariant.id.asc())
    ).first()


def _plan_updates_for_pair(
    session: Session,
    issue: CatalogIssue,
    gcd: dict[str, Any],
    *,
    ctx: CatalogCacheContext,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Return (planned_updates, conflicts, projected_upc_inserts)."""
    planned: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    upc_inserts = 0

    if extract_gcd_issue_id(issue.external_source_ids) is None and gcd.get("gcd_issue_id"):
        planned.append(
            {
                "field": "external_source_ids.gcd_issue",
                "action": "fill_missing",
                "new": int(gcd["gcd_issue_id"]),
            }
        )

    if gcd.get("barcode"):
        norm = None
        from app.services.catalog_ingestion_service import normalize_upc

        norm = normalize_upc(str(gcd["barcode"]))
        has = _issue_has_upc(session, int(issue.id or 0))
        if not has and norm:
            if norm in ctx.learned_barcodes:
                conflicts.append({"field": "catalog_upc", "reason": "learned_barcode_guard", "barcode": norm})
            elif norm in ctx.upc_to_issue and ctx.upc_to_issue[norm] != int(issue.id or 0):
                conflicts.append({"field": "catalog_upc", "reason": "upc_mapped_elsewhere", "barcode": norm})
            else:
                upc_inserts = 1
                planned.append({"field": "catalog_upc", "action": "insert", "new": str(gcd["barcode"])})

    cal = gcd.get("calendar_date")
    if cal and is_blank(issue.cover_date):
        planned.append({"field": "cover_date", "action": "fill_missing", "new": cal.isoformat()})
    if cal and is_blank(issue.release_date):
        planned.append({"field": "release_date", "action": "fill_missing", "new": cal.isoformat()})
    if cal and is_blank(issue.store_date):
        planned.append({"field": "store_date", "action": "fill_missing", "new": cal.isoformat()})

    if is_blank(issue.title) and gcd.get("title"):
        planned.append({"field": "title", "action": "fill_missing", "new": gcd["title"]})
    if is_blank(issue.description) and gcd.get("notes"):
        planned.append({"field": "description", "action": "fill_missing", "new": gcd["notes"]})

    variant = _primary_variant(session, int(issue.id or 0))
    if variant is not None:
        if is_blank(variant.printing) and gcd.get("printing_label"):
            planned.append({"field": "variant.printing", "action": "fill_missing", "new": gcd["printing_label"]})
        if is_blank(variant.variant_name) and gcd.get("variant_label"):
            planned.append({"field": "variant.variant_name", "action": "fill_missing", "new": gcd["variant_label"]})

    # Identity conflicts (report only — never write in P103)
    if gcd.get("issue_number") and issue.issue_number and str(issue.issue_number).strip() != str(gcd["issue_number"]).strip():
        conflicts.append(
            {
                "field": "issue_number",
                "reason": "higher_confidence_not_applied",
                "catalog": issue.issue_number,
                "gcd": gcd["issue_number"],
            }
        )

    series_row = session.get(CatalogSeries, int(issue.series_id or 0)) if issue.series_id else None
    if series_row and gcd.get("series"):
        if normalize_series_name(series_row.name) != normalize_series_name(gcd["series"]):
            conflicts.append(
                {
                    "field": "series",
                    "reason": "higher_confidence_not_applied",
                    "catalog": series_row.name,
                    "gcd": gcd["series"],
                }
            )
    pub_row = session.get(CatalogPublisher, int(issue.publisher_id or 0)) if issue.publisher_id else None
    if pub_row and gcd.get("publisher"):
        if normalize_series_name(pub_row.name) != normalize_series_name(gcd["publisher"]):
            conflicts.append(
                {
                    "field": "publisher",
                    "reason": "higher_confidence_not_applied",
                    "catalog": pub_row.name,
                    "gcd": gcd["publisher"],
                }
            )

    return planned, conflicts, upc_inserts


def run_p103_enrichment_dryrun(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    sample_limit: int = 50,
    use_fast_path: bool = True,
    benchmark: bool = False,
) -> P103DryRunReport:
    from app.services.p103_gcd_enrichment_fast import enrichment_cache_ready, run_p103_enrichment_dryrun_fast

    if filters.all_catalog:
        if not enrichment_cache_ready(cache_path):
            raise ValueError(
                "--all requires catalog_enrichment_issue cache; run with --refresh-cache."
            )
        use_fast_path = True

    if use_fast_path and enrichment_cache_ready(cache_path):
        report, timer = run_p103_enrichment_dryrun_fast(
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            sample_limit=sample_limit,
            benchmark=benchmark,
        )
        if timer is not None:
            report.perf = timer.to_dict()
        return report

    t0 = time.perf_counter()
    report = P103DryRunReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        gcd_database=str(gcd_path),
        catalog_cache=str(cache_path),
        filters={
            **enrichment_filters_to_dict(filters),
        },
    )
    ctx = CatalogCacheContext.load(cache_path)
    from app.models.intake_queue import ComicIssueBarcode

    learned = {
        str(bc)
        for bc in session.exec(select(ComicIssueBarcode.normalized_barcode)).all()
        if bc
    }
    ctx.learned_barcodes = learned
    updates_by_field: Counter[str] = Counter()

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
        """,
        (filters.year_from, filters.year_to),
    )

    seen_issues: set[int] = set()
    processed = 0

    while True:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for row in batch:
            if filters.limit is not None and processed >= filters.limit:
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
            if issue_id is None:
                report.skipped_no_catalog_match += 1
                continue

            if issue_id in seen_issues:
                continue
            seen_issues.add(issue_id)
            processed += 1
            report.catalog_issues_in_scope += 1
            report.matched_to_gcd += 1

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

            if extract_gcd_issue_id(issue.external_source_ids) is None:
                report.missing_gcd_ids += 1
            if not _issue_has_upc(session, issue_id) and gcd_inputs.get("barcode"):
                report.missing_upc += 1
            if (
                is_blank(issue.cover_date)
                or is_blank(issue.release_date)
                or is_blank(issue.store_date)
            ) and gcd_inputs.get("calendar_date"):
                report.missing_dates += 1
            if is_blank(issue.title) and gcd_inputs.get("title"):
                report.missing_titles += 1
            if is_blank(issue.description) and gcd_inputs.get("notes"):
                report.missing_notes += 1

            variant = _primary_variant(session, issue_id)
            if variant is not None:
                if is_blank(variant.printing) and gcd_inputs.get("printing_label"):
                    report.missing_printing += 1
                if is_blank(variant.variant_name) and gcd_inputs.get("variant_label"):
                    report.missing_variants += 1

            planned, conflicts, upc_n = _plan_updates_for_pair(session, issue, gcd_inputs, ctx=ctx)
            report.projected_upc_inserts += upc_n
            report.projected_field_updates += len(planned)
            report.conflicts += len(conflicts)
            for p in planned:
                updates_by_field[p["field"]] += 1
            if conflicts and len(report.conflict_samples) < 20:
                report.conflict_samples.append(
                    {
                        "catalog_issue_id": issue_id,
                        "gcd_issue_id": int(gcd_issue_id),
                        "conflicts": conflicts,
                    }
                )
            if planned and len(report.sample_updates) < sample_limit:
                report.sample_updates.append(
                    {
                        "catalog_issue_id": issue_id,
                        "gcd_issue_id": int(gcd_issue_id),
                        "series": series_name,
                        "issue_number": number,
                        "planned": planned,
                    }
                )

        if filters.limit is not None and processed >= filters.limit:
            break

    conn.close()
    report.updates_by_field = dict(updates_by_field)
    report.elapsed_seconds = round(time.perf_counter() - t0, 2)
    return report
