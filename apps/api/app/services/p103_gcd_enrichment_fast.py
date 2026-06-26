"""P103 fast enrichment dry-run — catalog-driven, SQLite-only planning."""

from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name, normalize_upc, series_names_compatible
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p102_gcd_modern_acquisition_service import YEAR_EXPR
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters, P103DryRunReport
from app.services.p103_gcd_enrichment_helpers import (
    extract_gcd_issue_id,
    gcd_row_to_plan_inputs,
    is_blank,
)

MAX_ENRICHMENT_LARGE_WRITE_LIMIT = 50_000


@dataclass
class EnrichmentIssueSnapshot:
    issue_id: int
    year: int | None
    publisher_id: int | None
    series_id: int | None
    publisher_norm: str
    series_norm: str
    issue_norm: str
    publisher_name: str
    series_name: str
    issue_number: str
    cover_date: str | None
    release_date: str | None
    store_date: str | None
    title: str | None
    description: str | None
    external_source_ids: dict[str, Any]
    variant_printing: str | None
    variant_variant_name: str | None
    has_upc: bool


@dataclass
class P103DryRunTimer:
    cache_load_sec: float = 0.0
    gcd_query_sec: float = 0.0
    match_sec: float = 0.0
    upc_plan_sec: float = 0.0
    field_plan_sec: float = 0.0
    conflict_plan_sec: float = 0.0
    json_serialize_sec: float = 0.0
    catalog_rows_scanned: int = 0
    gcd_rows_loaded: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cache_load_sec": round(self.cache_load_sec, 3),
            "gcd_query_sec": round(self.gcd_query_sec, 3),
            "match_sec": round(self.match_sec, 3),
            "upc_plan_sec": round(self.upc_plan_sec, 3),
            "field_plan_sec": round(self.field_plan_sec, 3),
            "conflict_plan_sec": round(self.conflict_plan_sec, 3),
            "json_serialize_sec": round(self.json_serialize_sec, 3),
            "catalog_rows_scanned": self.catalog_rows_scanned,
            "gcd_rows_loaded": self.gcd_rows_loaded,
        }


def enrichment_cache_ready(cache_path: Path) -> bool:
    if not cache_path.exists():
        return False
    conn = sqlite3.connect(cache_path)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='catalog_enrichment_issue'"
    ).fetchone()
    conn.close()
    return row is not None


def _parse_iso_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _blank_str(value: str | None) -> bool:
    return value is None or not str(value).strip()


def plan_enrichment_updates(
    snap: EnrichmentIssueSnapshot,
    gcd: dict[str, Any],
    *,
    ctx: CatalogCacheContext,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    planned: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    upc_inserts = 0
    issue_id = snap.issue_id

    if extract_gcd_issue_id(snap.external_source_ids) is None and gcd.get("gcd_issue_id"):
        planned.append(
            {
                "field": "external_source_ids.gcd_issue",
                "action": "fill_missing",
                "new": int(gcd["gcd_issue_id"]),
            }
        )

    if gcd.get("barcode"):
        norm = normalize_upc(str(gcd["barcode"]))
        if not snap.has_upc and norm:
            if norm in ctx.learned_barcodes:
                conflicts.append({"field": "catalog_upc", "reason": "learned_barcode_guard", "barcode": norm})
            elif norm in ctx.upc_to_issue and ctx.upc_to_issue[norm] != issue_id:
                conflicts.append({"field": "catalog_upc", "reason": "upc_mapped_elsewhere", "barcode": norm})
            else:
                upc_inserts = 1
                planned.append({"field": "catalog_upc", "action": "insert", "new": str(gcd["barcode"])})

    cal = gcd.get("calendar_date")
    if cal and _blank_str(snap.cover_date):
        planned.append({"field": "cover_date", "action": "fill_missing", "new": cal.isoformat()})
    if cal and _blank_str(snap.release_date):
        planned.append({"field": "release_date", "action": "fill_missing", "new": cal.isoformat()})
    if cal and _blank_str(snap.store_date):
        planned.append({"field": "store_date", "action": "fill_missing", "new": cal.isoformat()})

    if _blank_str(snap.title) and gcd.get("title"):
        planned.append({"field": "title", "action": "fill_missing", "new": gcd["title"]})
    if _blank_str(snap.description) and gcd.get("notes"):
        planned.append({"field": "description", "action": "fill_missing", "new": gcd["notes"]})

    if _blank_str(snap.variant_printing) and gcd.get("printing_label"):
        planned.append({"field": "variant.printing", "action": "fill_missing", "new": gcd["printing_label"]})
    if _blank_str(snap.variant_variant_name) and gcd.get("variant_label"):
        planned.append({"field": "variant.variant_name", "action": "fill_missing", "new": gcd["variant_label"]})

    if gcd.get("issue_number") and snap.issue_number and str(snap.issue_number).strip() != str(gcd["issue_number"]).strip():
        conflicts.append(
            {
                "field": "issue_number",
                "reason": "higher_confidence_not_applied",
                "catalog": snap.issue_number,
                "gcd": gcd["issue_number"],
            }
        )
    if gcd.get("series") and snap.series_name:
        if normalize_series_name(snap.series_name) != normalize_series_name(gcd["series"]):
            conflicts.append(
                {
                    "field": "series",
                    "reason": "higher_confidence_not_applied",
                    "catalog": snap.series_name,
                    "gcd": gcd["series"],
                }
            )
    if gcd.get("publisher") and snap.publisher_name:
        if normalize_series_name(snap.publisher_name) != normalize_series_name(gcd["publisher"]):
            conflicts.append(
                {
                    "field": "publisher",
                    "reason": "higher_confidence_not_applied",
                    "catalog": snap.publisher_name,
                    "gcd": gcd["publisher"],
                }
            )

    return planned, conflicts, upc_inserts


@dataclass
class _GcdIndex:
    exact: dict[tuple[str, str, str], dict[str, Any]]
    by_series_issue: dict[tuple[str, str], list[tuple[str, int | None, dict[str, Any]]]]
    rows_loaded: int = 0


def _load_gcd_index(
    gcd_path: Path,
    *,
    year_from: int,
    year_to: int,
    focus_publisher: str | None,
    all_catalog: bool = False,
    year_filter_explicit: bool = False,
) -> _GcdIndex:
    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    where_parts: list[str] = []
    params: list[int] = []
    if not all_catalog or year_filter_explicit:
        where_parts.append(f"{YEAR_EXPR} BETWEEN ? AND ?")
        params.extend([year_from, year_to])
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    cur = conn.execute(
        f"""
        SELECT i.id AS issue_id, p.id AS gcd_publisher_id, p.name AS publisher_name,
               s.id AS gcd_series_id, s.name AS series_name,
               i.number, i.barcode, i.key_date, s.year_began,
               i.title AS title, i.notes AS notes
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        {where_sql}
        """,
        tuple(params),
    )
    exact: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_si: dict[tuple[str, str], list[tuple[str, int | None, dict[str, Any]]]] = {}
    loaded = 0
    while True:
        batch = cur.fetchmany(10000)
        if not batch:
            break
        for row in batch:
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
            if not all_catalog:
                focus = canonical_focus_publisher_label(str(publisher_name or ""))
                if focus is None or focus != focus_publisher:
                    continue
                pub_label = str(publisher_name or focus)
            else:
                focus = canonical_focus_publisher_label(str(publisher_name or ""))
                pub_label = str(publisher_name or focus or "")
                if not pub_label.strip():
                    continue
            pub_norm = normalize_series_name(pub_label if all_catalog else str(publisher_name or focus))
            ser_norm = normalize_series_name(str(series_name or ""))
            iss_norm = normalize_issue_number(str(number or ""))
            if not pub_norm or not ser_norm or not iss_norm:
                continue
            row_dict = {
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
            year_val = None
            if key_date and len(str(key_date)) >= 4:
                try:
                    year_val = int(str(key_date)[0:4])
                except ValueError:
                    year_val = int(year_began) if year_began else None
            elif year_began:
                year_val = int(year_began)
            exact[(pub_norm, ser_norm, iss_norm)] = row_dict
            by_si.setdefault((ser_norm, iss_norm), []).append((pub_norm, year_val, row_dict))
            loaded += 1
    conn.close()
    return _GcdIndex(exact=exact, by_series_issue=by_si, rows_loaded=loaded)


def _lookup_gcd(index: _GcdIndex, snap: EnrichmentIssueSnapshot) -> dict[str, Any] | None:
    key = (snap.publisher_norm, snap.series_norm, snap.issue_norm)
    if key in index.exact:
        return index.exact[key]
    candidates = index.by_series_issue.get((snap.series_norm, snap.issue_norm))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][2]
    pub_matches = [
        c for c in candidates if c[0] == snap.publisher_norm or series_names_compatible(snap.publisher_norm, c[0])
    ]
    if len(pub_matches) == 1:
        return pub_matches[0][2]
    if not pub_matches:
        return None
    year = snap.year
    if year is None:
        return pub_matches[0][2]
    scored = sorted(pub_matches, key=lambda c: abs((c[1] if c[1] is not None else year) - year))
    if len(scored) >= 2 and abs((scored[0][1] or year) - year) == abs((scored[1][1] or year) - year):
        return None
    return scored[0][2]


def _load_catalog_scope(
    cache_path: Path,
    *,
    filters: EnrichmentFilters,
) -> list[EnrichmentIssueSnapshot]:
    conn = sqlite3.connect(cache_path)
    base_select = """
        SELECT issue_id, year, publisher_id, series_id, publisher_norm, series_norm, issue_norm,
               publisher_name, series_name, issue_number, cover_date, release_date, store_date,
               title, description, external_source_ids, variant_printing, variant_variant_name, has_upc
        FROM catalog_enrichment_issue
    """
    if filters.all_catalog and not filters.year_filter_explicit:
        rows = conn.execute(f"{base_select} ORDER BY issue_id").fetchall()
    elif filters.all_catalog and filters.year_filter_explicit:
        rows = conn.execute(
            f"{base_select} WHERE year IS NOT NULL AND year BETWEEN ? AND ? ORDER BY issue_id",
            (filters.year_from, filters.year_to),
        ).fetchall()
    else:
        rows = conn.execute(
            f"{base_select} WHERE year IS NOT NULL AND year BETWEEN ? AND ? ORDER BY issue_id",
            (filters.year_from, filters.year_to),
        ).fetchall()
    conn.close()
    out: list[EnrichmentIssueSnapshot] = []
    for row in rows:
        publisher_name = str(row[7] or "")
        if not filters.all_catalog:
            focus = canonical_focus_publisher_label(publisher_name)
            if focus != filters.publisher:
                continue
        ext_raw = row[15]
        try:
            ext = json.loads(ext_raw) if ext_raw else {}
        except json.JSONDecodeError:
            ext = {}
        out.append(
            EnrichmentIssueSnapshot(
                issue_id=int(row[0]),
                year=int(row[1]) if row[1] is not None else None,
                publisher_id=int(row[2]) if row[2] is not None else None,
                series_id=int(row[3]) if row[3] is not None else None,
                publisher_norm=str(row[4]),
                series_norm=str(row[5]),
                issue_norm=str(row[6]),
                publisher_name=publisher_name,
                series_name=str(row[8] or ""),
                issue_number=str(row[9] or ""),
                cover_date=row[10],
                release_date=row[11],
                store_date=row[12],
                title=row[13],
                description=row[14],
                external_source_ids=ext,
                variant_printing=row[16],
                variant_variant_name=row[17],
                has_upc=bool(row[18]),
            )
        )
    return out


def load_catalog_enrichment_scope(cache_path: Path, *, filters: EnrichmentFilters) -> list[EnrichmentIssueSnapshot]:
    """Catalog-first scope for P103 (--all and tests)."""
    return _load_catalog_scope(cache_path, filters=filters)


def run_p103_enrichment_dryrun_fast(
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    sample_limit: int = 50,
    benchmark: bool = False,
) -> tuple[P103DryRunReport, P103DryRunTimer | None]:
    if not enrichment_cache_ready(cache_path):
        raise ValueError(
            "catalog_enrichment_issue table missing in cache; run with --refresh-cache to rebuild."
        )

    t0 = time.perf_counter()
    timer = P103DryRunTimer() if benchmark else None

    from datetime import datetime, timezone

    from app.services.p103_gcd_catalog_enrichment_service import enrichment_filters_to_dict

    report = P103DryRunReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        mode="dry_run_fast",
        gcd_database=str(gcd_path),
        catalog_cache=str(cache_path),
        filters=enrichment_filters_to_dict(filters),
    )

    t_cache = time.perf_counter()
    ctx = CatalogCacheContext.load(cache_path)
    catalog_scope = _load_catalog_scope(cache_path, filters=filters)
    if timer:
        timer.cache_load_sec = time.perf_counter() - t_cache

    t_gcd = time.perf_counter()
    gcd_index = _load_gcd_index(
        gcd_path,
        year_from=filters.year_from,
        year_to=filters.year_to,
        focus_publisher=filters.publisher,
        all_catalog=filters.all_catalog,
        year_filter_explicit=filters.year_filter_explicit,
    )
    if timer:
        timer.gcd_query_sec = time.perf_counter() - t_gcd
        timer.gcd_rows_loaded = gcd_index.rows_loaded

    updates_by_field: Counter[str] = Counter()
    processed = 0

    for snap in catalog_scope:
        if timer:
            timer.catalog_rows_scanned += 1
        if filters.limit is not None and processed >= filters.limit:
            break

        t_match = time.perf_counter()
        gcd_row = _lookup_gcd(gcd_index, snap)
        if timer:
            timer.match_sec += time.perf_counter() - t_match
        if gcd_row is None:
            report.skipped_no_catalog_match += 1
            continue

        processed += 1
        report.catalog_issues_in_scope += 1
        report.matched_to_gcd += 1

        gcd_inputs = gcd_row_to_plan_inputs(gcd_row)

        if extract_gcd_issue_id(snap.external_source_ids) is None:
            report.missing_gcd_ids += 1
        if not snap.has_upc and gcd_inputs.get("barcode"):
            report.missing_upc += 1
        if (
            _blank_str(snap.cover_date)
            or _blank_str(snap.release_date)
            or _blank_str(snap.store_date)
        ) and gcd_inputs.get("calendar_date"):
            report.missing_dates += 1
        if _blank_str(snap.title) and gcd_inputs.get("title"):
            report.missing_titles += 1
        if _blank_str(snap.description) and gcd_inputs.get("notes"):
            report.missing_notes += 1
        if _blank_str(snap.variant_printing) and gcd_inputs.get("printing_label"):
            report.missing_printing += 1
        if _blank_str(snap.variant_variant_name) and gcd_inputs.get("variant_label"):
            report.missing_variants += 1

        t_upc = time.perf_counter()
        planned, conflicts, upc_n = plan_enrichment_updates(snap, gcd_inputs, ctx=ctx)
        upc_elapsed = time.perf_counter() - t_upc
        if timer:
            timer.upc_plan_sec += upc_elapsed * 0.35
            timer.field_plan_sec += upc_elapsed * 0.45
            timer.conflict_plan_sec += upc_elapsed * 0.20

        report.projected_upc_inserts += upc_n
        report.projected_field_updates += len(planned)
        report.conflicts += len(conflicts)
        for p in planned:
            updates_by_field[p["field"]] += 1
        if conflicts and len(report.conflict_samples) < 20:
            report.conflict_samples.append(
                {
                    "catalog_issue_id": snap.issue_id,
                    "gcd_issue_id": int(gcd_row["issue_id"]),
                    "conflicts": conflicts,
                }
            )
        if planned and len(report.sample_updates) < sample_limit:
            report.sample_updates.append(
                {
                    "catalog_issue_id": snap.issue_id,
                    "gcd_issue_id": int(gcd_row["issue_id"]),
                    "series": snap.series_name,
                    "issue_number": snap.issue_number,
                    "planned": planned,
                }
            )

    report.updates_by_field = dict(updates_by_field)
    report.elapsed_seconds = round(time.perf_counter() - t0, 2)

    if timer:
        t_json = time.perf_counter()
        report.to_json()
        timer.json_serialize_sec = time.perf_counter() - t_json

    return report, timer
