"""P103 controlled enrichment write-batch (update catalog_issue only; max 100 rows)."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode
from app.services.catalog_ingestion_service import merge_external_ids, normalize_issue_number, normalize_series_name, normalize_upc
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS, YEAR_EXPR
from app.services.p103_gcd_catalog_enrichment_service import (
    EnrichmentFilters,
    MAX_ENRICHMENT_WRITE_LIMIT,
    _plan_updates_for_pair,
    validate_enrichment_filters,
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

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "report_at": self.report_at,
            "filters": self.filters,
            "updated_issues": self.updated_issues,
            "inserted_upcs": self.inserted_upcs,
            "skipped_no_updates": self.skipped_no_updates,
            "skipped_conflicts": self.skipped_conflicts,
            "errors": self.errors,
            "written_rows": self.written_rows,
        }


def _reload_barcode_guard(session: Session) -> tuple[set[str], dict[str, int]]:
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
    return learned, upc_map


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


def _insert_upc_if_allowed(
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
    if normalized in upc_map and upc_map[normalized] != issue_id:
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


def _apply_planned_updates(
    session: Session,
    issue: CatalogIssue,
    variant: CatalogVariant | None,
    planned: list[dict[str, Any]],
    *,
    learned: set[str],
    upc_map: dict[str, int],
) -> tuple[int, int | None]:
    """Return (fields_updated_count, inserted_upc_id)."""
    fields_updated = 0
    upc_id: int | None = None
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
            upc_id = _insert_upc_if_allowed(
                session,
                raw_upc=str(item["new"]),
                issue_id=issue_id,
                variant_id=variant_id,
                learned=learned,
                upc_map=upc_map,
            )

    if variant is not None:
        session.add(variant)
    session.add(issue)
    return fields_updated, upc_id


def run_p103_enrichment_write_batch(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    rollback_collector: dict[str, Any] | None = None,
) -> P103WriteBatchReport:
    if filters.limit is None or filters.limit > MAX_ENRICHMENT_WRITE_LIMIT:
        raise ValueError(f"P103 write limit must be 1–{MAX_ENRICHMENT_WRITE_LIMIT}")

    report = P103WriteBatchReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        filters={
            "publisher": filters.publisher,
            "year_from": filters.year_from,
            "year_to": filters.year_to,
            "limit": filters.limit,
        },
    )

    ctx = CatalogCacheContext.load(cache_path)
    learned, upc_map = _reload_barcode_guard(session)
    ctx.learned_barcodes = learned
    ctx.upc_to_issue = upc_map

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
                fields_updated, upc_id = _apply_planned_updates(
                    session,
                    issue,
                    variant,
                    planned,
                    learned=learned,
                    upc_map=upc_map,
                )
                if fields_updated == 0 and upc_id is None:
                    report.skipped_no_updates += 1
                    session.rollback()
                    continue

                session.commit()
                seen_issues.add(issue_id)
                written += 1
                report.updated_issues += 1
                inserted_upc = upc_id is not None
                if inserted_upc:
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
                    if upc_id is not None:
                        rollback_collector.setdefault("upc_ids", []).append(upc_id)

                report.written_rows.append(
                    {
                        "gcd_issue_id": int(gcd_issue_id),
                        "catalog_issue_id": issue_id,
                        "series": series_name,
                        "issue_number": number,
                        "fields_updated": fields_updated,
                        "inserted_upc": inserted_upc,
                        "barcode": gcd_inputs.get("barcode"),
                    }
                )
            except Exception as exc:
                session.rollback()
                report.errors.append(f"catalog_issue_id={issue_id}: {exc}")
                learned, upc_map = _reload_barcode_guard(session)
                ctx.learned_barcodes = learned
                ctx.upc_to_issue = upc_map

    conn.close()
    return report
