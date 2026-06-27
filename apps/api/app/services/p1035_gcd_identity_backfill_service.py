"""P103.5 / P105.5 — GCD identity + UPC backfill for existing catalog_issue rows only."""

from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogVariant
from app.models.catalog_p97 import CatalogImportJob
from app.models.intake_queue import ComicIssueBarcode
from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.catalog_ingestion_service import merge_external_ids, normalize_upc
from app.services.gcd_barcode_import_service import GCD_SOURCE
from app.services.gcd_catalog_upc_insert_service import insert_catalog_upc_if_absent, preload_catalog_upc_guards
from app.services.p101_catalog_cache_service import CatalogCacheContext
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters, enrichment_filters_to_dict
from app.services.p103_gcd_enrichment_fast import (
    EnrichmentIssueSnapshot,
    _GcdIndex,
    load_catalog_enrichment_scope,
    load_gcd_index_for_enrichment,
)
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id, gcd_row_to_plan_inputs
from app.services.catalog_ingestion_service import series_names_compatible

P1035_JOB_TYPE_DRY_RUN = "gcd_identity_backfill_dry_run"
P1035_JOB_TYPE_WRITE = "gcd_identity_backfill_write"

_YEAR_TOKEN = re.compile(r"^(19|20)\d{2}$")


def _series_norm_aliases(series_norm: str) -> list[str]:
    norms = [series_norm]
    parts = series_norm.split()
    if len(parts) >= 2 and _YEAR_TOKEN.fullmatch(parts[-1]):
        base = " ".join(parts[:-1]).strip()
        if base and base not in norms:
            norms.append(base)
    return norms


def _expand_scope_for_gcd_index(scope: Sequence[EnrichmentIssueSnapshot]) -> list[EnrichmentIssueSnapshot]:
    expanded: list[EnrichmentIssueSnapshot] = []
    seen: set[tuple[int, str]] = set()
    for snap in scope:
        for ser in _series_norm_aliases(snap.series_norm):
            key = (snap.issue_id, ser)
            if key in seen:
                continue
            seen.add(key)
            if ser == snap.series_norm:
                expanded.append(snap)
            else:
                expanded.append(
                    EnrichmentIssueSnapshot(
                        issue_id=snap.issue_id,
                        year=snap.year,
                        publisher_id=snap.publisher_id,
                        series_id=snap.series_id,
                        publisher_norm=snap.publisher_norm,
                        series_norm=ser,
                        issue_norm=snap.issue_norm,
                        publisher_name=snap.publisher_name,
                        series_name=snap.series_name,
                        issue_number=snap.issue_number,
                        cover_date=snap.cover_date,
                        release_date=snap.release_date,
                        store_date=snap.store_date,
                        title=snap.title,
                        description=snap.description,
                        external_source_ids=snap.external_source_ids,
                        variant_printing=snap.variant_printing,
                        variant_variant_name=snap.variant_variant_name,
                        has_upc=snap.has_upc,
                    )
                )
    return expanded


def lookup_gcd_for_catalog(index: _GcdIndex, snap: EnrichmentIssueSnapshot) -> dict[str, Any] | None:
    """Match GCD row with series year-suffix aliases (e.g. superman 2016 → superman)."""
    publisher_norms = [snap.publisher_norm]
    for pub in publisher_norms:
        for ser in _series_norm_aliases(snap.series_norm):
            key = (pub, ser, snap.issue_norm)
            if key in index.exact:
                return index.exact[key]
    for ser in _series_norm_aliases(snap.series_norm):
        candidates = index.by_series_issue.get((ser, snap.issue_norm))
        if not candidates:
            continue
        if len(candidates) == 1:
            return candidates[0][2]
        pub_matches = [
            c
            for c in candidates
            if c[0] == snap.publisher_norm or series_names_compatible(snap.publisher_norm, c[0])
        ]
        if len(pub_matches) == 1:
            return pub_matches[0][2]
        if not pub_matches:
            continue
        year = snap.year
        if year is None:
            if len(pub_matches) > 1:
                return None
            return pub_matches[0][2]
        scored = sorted(pub_matches, key=lambda c: abs((c[1] if c[1] is not None else year) - year))
        if len(scored) >= 2 and abs((scored[0][1] or year) - year) == abs((scored[1][1] or year) - year):
            return None
        return scored[0][2]
    return None


def _comicvine_ids(external: dict[str, Any]) -> list[str]:
    bucket = external.get("COMICVINE") if isinstance(external, dict) else None
    if not isinstance(bucket, dict):
        return []
    return [str(k) for k in bucket if str(k).isdigit()]


def load_resume_catalog_issue_ids(session: Session, job_id: int) -> set[int]:
    job = session.get(CatalogImportJob, job_id)
    if job is None:
        raise ValueError(f"resume job {job_id} not found")
    cfg = dict(job.config or {})
    report = dict(cfg.get("report") or {})
    ids: set[int] = set()
    for row in report.get("written_rows") or []:
        iid = row.get("catalog_issue_id")
        if iid is not None:
            ids.add(int(iid))
    for snap in (cfg.get("rollback") or {}).get("issue_snapshots") or []:
        iid = snap.get("catalog_issue_id")
        if iid is not None:
            ids.add(int(iid))
    return ids


def build_comicvine_duplicate_index(
    scope: Sequence[EnrichmentIssueSnapshot],
) -> dict[str, list[int]]:
    by_cv: dict[str, list[int]] = defaultdict(list)
    for snap in scope:
        for cv_id in _comicvine_ids(snap.external_source_ids):
            by_cv[cv_id].append(int(snap.issue_id))
    return {k: v for k, v in by_cv.items() if len(v) > 1}


def _attach_gcd_meta(existing: dict | None, *, series_id: int | None, publisher_id: int | None) -> dict:
    payload = dict(existing or {})
    meta = dict(payload.get("_gcd") or {})
    if series_id is not None:
        meta["series_id"] = int(series_id)
    if publisher_id is not None:
        meta["publisher_id"] = int(publisher_id)
    payload["_gcd"] = meta
    return payload


@dataclass
class P1035DryRunReport:
    mode: str = "identity_backfill_dry_run"
    report_at: str = ""
    gcd_database: str = ""
    catalog_cache: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    existing_issues_scanned: int = 0
    missing_gcd_ids: int = 0
    matched_gcd_ids: int = 0
    projected_upc_inserts: int = 0
    ambiguous_skipped: int = 0
    duplicate_cv_conflicts: int = 0
    validation_failures: int = 0
    learned_barcode_conflicts: int = 0
    upc_elsewhere_conflicts: int = 0
    gcd_match_ties: int = 0
    skipped_no_gcd_match: int = 0
    skipped_already_has_gcd: int = 0
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    perf: dict[str, Any] | None = None
    candidate_scope: dict[str, int] | None = None

    def to_json(self) -> dict[str, Any]:
        payload = {
            "mode": self.mode,
            "report_at": self.report_at,
            "gcd_database": self.gcd_database,
            "catalog_cache": self.catalog_cache,
            "filters": self.filters,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "existing_issues_scanned": self.existing_issues_scanned,
            "missing_gcd_ids": self.missing_gcd_ids,
            "matched_gcd_ids": self.matched_gcd_ids,
            "projected_upc_inserts": self.projected_upc_inserts,
            "ambiguous_skipped": self.ambiguous_skipped,
            "duplicate_cv_conflicts": self.duplicate_cv_conflicts,
            "validation_failures": self.validation_failures,
            "learned_barcode_conflicts": self.learned_barcode_conflicts,
            "upc_elsewhere_conflicts": self.upc_elsewhere_conflicts,
            "gcd_match_ties": self.gcd_match_ties,
            "skipped_no_gcd_match": self.skipped_no_gcd_match,
            "skipped_already_has_gcd": self.skipped_already_has_gcd,
            "sample_rows": self.sample_rows,
            "perf": self.perf,
        }
        if self.candidate_scope is not None:
            payload["candidate_scope"] = self.candidate_scope
        return payload


@dataclass
class P1035WriteReport:
    mode: str = "identity_backfill_write"
    report_at: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    updated_issues: int = 0
    inserted_upcs: int = 0
    skipped_no_updates: int = 0
    skipped_conflicts: int = 0
    validation_failures: int = 0
    duplicate_cv_conflicts: int = 0
    ambiguous_skipped: int = 0
    learned_barcode_conflicts: int = 0
    errors: list[str] = field(default_factory=list)
    written_rows: list[dict[str, Any]] = field(default_factory=list)
    scanned: int = 0
    matched: int = 0
    perf: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "report_at": self.report_at,
            "filters": self.filters,
            "updated_issues": self.updated_issues,
            "inserted_upcs": self.inserted_upcs,
            "skipped_no_updates": self.skipped_no_updates,
            "skipped_conflicts": self.skipped_conflicts,
            "validation_failures": self.validation_failures,
            "duplicate_cv_conflicts": self.duplicate_cv_conflicts,
            "ambiguous_skipped": self.ambiguous_skipped,
            "errors": self.errors,
            "written_rows": self.written_rows,
            "scanned": self.scanned,
            "matched": self.matched,
            "perf": self.perf,
        }


def _filter_missing_gcd(scope: list[EnrichmentIssueSnapshot]) -> list[EnrichmentIssueSnapshot]:
    return [s for s in scope if extract_gcd_issue_id(s.external_source_ids) is None]


@dataclass
class P1035CandidateScopeStats:
    total_catalog_issues: int = 0
    without_gcd_id: int = 0
    after_publisher_filter: int = 0
    after_year_filter: int = 0
    after_resume_filter: int = 0
    final_candidates: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_catalog_issues": self.total_catalog_issues,
            "without_gcd_id": self.without_gcd_id,
            "after_publisher_filter": self.after_publisher_filter,
            "after_year_filter": self.after_year_filter,
            "after_resume_filter": self.after_resume_filter,
            "final_candidates": self.final_candidates,
        }


def analyze_p1035_candidate_scope(
    cache_path: Path,
    filters: EnrichmentFilters,
    skip_issue_ids: set[int] | None = None,
) -> P1035CandidateScopeStats:
    from app.services.p103_gcd_enrichment_fast import load_catalog_enrichment_rows, _snapshot_from_enrichment_row

    skip = skip_issue_ids or set()
    stats = P1035CandidateScopeStats()
    rows = load_catalog_enrichment_rows(cache_path)
    stats.total_catalog_issues = len(rows)

    missing_gcd: list[EnrichmentIssueSnapshot] = []
    for row in rows:
        snap = _snapshot_from_enrichment_row(row)
        if extract_gcd_issue_id(snap.external_source_ids) is None:
            missing_gcd.append(snap)
    stats.without_gcd_id = len(missing_gcd)

    after_pub: list[EnrichmentIssueSnapshot] = []
    for snap in missing_gcd:
        if not filters.all_catalog:
            focus = canonical_focus_publisher_label(snap.publisher_name)
            if focus != filters.publisher:
                continue
        after_pub.append(snap)
    stats.after_publisher_filter = len(after_pub)

    after_year: list[EnrichmentIssueSnapshot] = []
    for snap in after_pub:
        if filters.year_filter_explicit:
            if snap.year is None or snap.year < filters.year_from or snap.year > filters.year_to:
                continue
        after_year.append(snap)
    stats.after_year_filter = len(after_year)

    after_resume = [s for s in after_year if int(s.issue_id) not in skip]
    stats.after_resume_filter = len(after_resume)
    stats.final_candidates = len(after_resume)
    return stats


def format_p1035_candidate_scope_report(stats: P1035CandidateScopeStats) -> str:
    lines = [
        "P103.5 candidate scope:",
        f"  total_catalog_issues: {stats.total_catalog_issues:,}",
        f"  without_gcd_id: {stats.without_gcd_id:,}",
        f"  after_publisher_filter: {stats.after_publisher_filter:,}",
        f"  after_year_filter: {stats.after_year_filter:,}",
        f"  after_resume_filter: {stats.after_resume_filter:,}",
        f"  final_candidates: {stats.final_candidates:,}",
    ]
    return "\n".join(lines)


def _normalize_gcd_inputs(gcd_row: dict[str, Any]) -> dict[str, Any]:
    if gcd_row.get("gcd_issue_id") is not None:
        return gcd_row
    return gcd_row_to_plan_inputs(gcd_row)


def plan_identity_backfill(
    snap: EnrichmentIssueSnapshot,
    gcd_row: dict[str, Any],
    *,
    ctx: CatalogCacheContext,
) -> tuple[list[dict[str, Any]], str | None, int]:
    """Identity-only plan: GCD ids + optional catalog_upc (validated)."""
    gcd_inputs = _normalize_gcd_inputs(gcd_row)
    planned: list[dict[str, Any]] = []
    upc_n = 0

    if extract_gcd_issue_id(snap.external_source_ids) is not None:
        return [], "already_has_gcd", 0

    gcd_issue_id = int(gcd_inputs["gcd_issue_id"])
    planned.append(
        {"field": "external_source_ids.gcd_issue", "action": "fill_missing", "new": gcd_issue_id}
    )
    if gcd_inputs.get("gcd_series_id") or gcd_inputs.get("gcd_publisher_id"):
        planned.append(
            {
                "field": "external_source_ids._gcd_meta",
                "action": "fill_missing",
                "gcd_series_id": gcd_inputs.get("gcd_series_id"),
                "gcd_publisher_id": gcd_inputs.get("gcd_publisher_id"),
            }
        )

    barcode = gcd_inputs.get("barcode")
    if barcode and not snap.has_upc:
        norm = normalize_upc(str(barcode))
        if not norm:
            return planned, None, upc_n
        validation = validate_barcode_catalog_match(
            norm,
            publisher=snap.publisher_name,
            issue_number=snap.issue_number,
            year=str(snap.year or ""),
        )
        if validation.status != "exact_match":
            return planned, "barcode_validation_failed", upc_n
        if norm in ctx.learned_barcodes:
            return [], "learned_barcode_conflict", 0
        if norm in ctx.upc_to_issue and ctx.upc_to_issue[norm] != snap.issue_id:
            return [], "upc_mapped_elsewhere", 0
        upc_n = 1
        planned.append({"field": "catalog_upc", "action": "insert", "new": str(barcode)})

    return planned, None, upc_n


def _cv_duplicate_conflict(snap: EnrichmentIssueSnapshot, dup_index: dict[str, list[int]]) -> bool:
    for cv_id in _comicvine_ids(snap.external_source_ids):
        if cv_id in dup_index and len(dup_index[cv_id]) > 1:
            return True
    return False


def run_p1035_identity_dryrun(
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    benchmark: bool = False,
    sample_limit: int = 50,
    skip_issue_ids: set[int] | None = None,
    scope_stats: P1035CandidateScopeStats | None = None,
) -> P1035DryRunReport:
    t0 = time.perf_counter()
    report = P1035DryRunReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        gcd_database=str(gcd_path),
        catalog_cache=str(cache_path),
        filters=enrichment_filters_to_dict(filters),
    )
    if scope_stats is not None:
        report.candidate_scope = scope_stats.to_dict()
    ctx = CatalogCacheContext.load(cache_path)
    full_scope = load_catalog_enrichment_scope(cache_path, filters=filters)
    scope = _filter_missing_gcd(full_scope)
    dup_index = build_comicvine_duplicate_index(full_scope)

    expanded = _expand_scope_for_gcd_index(scope)
    gcd_index = load_gcd_index_for_enrichment(
        gcd_path,
        year_from=filters.year_from,
        year_to=filters.year_to,
        focus_publisher=filters.publisher,
        all_catalog=filters.all_catalog,
        year_filter_explicit=filters.year_filter_explicit,
        catalog_scope=expanded,
    )

    skip_ids = skip_issue_ids or set()
    processed = 0
    for snap in scope:
        if int(snap.issue_id) in skip_ids:
            continue
        if filters.limit is not None and processed >= filters.limit:
            break
        report.existing_issues_scanned += 1
        report.missing_gcd_ids += 1

        if _cv_duplicate_conflict(snap, dup_index):
            report.duplicate_cv_conflicts += 1
            continue

        gcd_row = lookup_gcd_for_catalog(gcd_index, snap)
        if gcd_row is None:
            report.skipped_no_gcd_match += 1
            report.ambiguous_skipped += 1
            continue

        processed += 1
        report.matched_gcd_ids += 1
        planned, skip, upc_n = plan_identity_backfill(snap, gcd_row, ctx=ctx)
        if skip == "already_has_gcd":
            report.skipped_already_has_gcd += 1
            continue
        if skip == "learned_barcode_conflict":
            report.learned_barcode_conflicts += 1
            continue
        if skip == "upc_mapped_elsewhere":
            report.upc_elsewhere_conflicts += 1
            continue
        if skip == "barcode_validation_failed":
            report.validation_failures += 1
        report.projected_upc_inserts += upc_n
        if len(report.sample_rows) < sample_limit:
            gcd_inputs = _normalize_gcd_inputs(gcd_row)
            report.sample_rows.append(
                {
                    "catalog_issue_id": snap.issue_id,
                    "series": snap.series_name,
                    "issue_number": snap.issue_number,
                    "gcd_issue_id": gcd_inputs.get("gcd_issue_id"),
                    "barcode": gcd_inputs.get("barcode"),
                    "projected_upc": upc_n,
                    "skip": skip,
                }
            )

    report.elapsed_seconds = time.perf_counter() - t0
    if benchmark:
        report.perf = {"gcd_rows_loaded": gcd_index.rows_loaded, "scope_missing_gcd": len(scope)}
    return report


def _apply_identity_planned(
    session: Session,
    issue: CatalogIssue,
    variant: CatalogVariant | None,
    planned: list[dict[str, Any]],
    *,
    learned: set[str],
    upc_map: dict[str, int],
    upc_id_by_normalized: dict[str, int],
) -> tuple[int, int | None, bool]:
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
        elif field == "external_source_ids._gcd_meta":
            issue.external_source_ids = _attach_gcd_meta(
                issue.external_source_ids,
                series_id=item.get("gcd_series_id"),
                publisher_id=item.get("gcd_publisher_id"),
            )
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

    session.add(issue)
    return fields_updated, upc_id, upc_created


def run_p1035_identity_write(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    filters: EnrichmentFilters,
    rollback_collector: dict[str, Any] | None = None,
    skip_issue_ids: set[int] | None = None,
) -> P1035WriteReport:
    t0 = time.perf_counter()
    report = P1035WriteReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        filters=enrichment_filters_to_dict(filters),
    )
    ctx = CatalogCacheContext.load(cache_path)
    full_scope = load_catalog_enrichment_scope(cache_path, filters=filters)
    scope = _filter_missing_gcd(full_scope)
    dup_index = build_comicvine_duplicate_index(full_scope)
    expanded = _expand_scope_for_gcd_index(scope)
    gcd_index = load_gcd_index_for_enrichment(
        gcd_path,
        year_from=filters.year_from,
        year_to=filters.year_to,
        focus_publisher=filters.publisher,
        all_catalog=filters.all_catalog,
        year_filter_explicit=filters.year_filter_explicit,
        catalog_scope=expanded,
    )

    learned = {str(b) for b in session.exec(select(ComicIssueBarcode.normalized_barcode)).all() if b}
    upc_map, upc_id_by_normalized = preload_catalog_upc_guards(session)

    skip_ids = skip_issue_ids or set()
    processed = 0
    for snap in scope:
        if int(snap.issue_id) in skip_ids:
            continue
        if filters.limit is not None and processed >= filters.limit:
            break
        report.scanned += 1

        if _cv_duplicate_conflict(snap, dup_index):
            report.duplicate_cv_conflicts += 1
            report.skipped_conflicts += 1
            continue

        gcd_row = lookup_gcd_for_catalog(gcd_index, snap)
        if gcd_row is None:
            report.ambiguous_skipped += 1
            continue

        report.matched += 1
        planned, skip, _upc_n = plan_identity_backfill(snap, gcd_row, ctx=ctx)
        if skip == "learned_barcode_conflict":
            report.skipped_conflicts += 1
            report.learned_barcode_conflicts += 1
            continue
        if skip == "upc_mapped_elsewhere":
            report.skipped_conflicts += 1
            continue
        if skip == "barcode_validation_failed":
            report.validation_failures += 1
        if not planned:
            report.skipped_no_updates += 1
            continue

        issue = session.get(CatalogIssue, int(snap.issue_id))
        if issue is None:
            report.errors.append(f"missing catalog_issue_id={snap.issue_id}")
            continue
        variant = session.exec(
            select(CatalogVariant)
            .where(CatalogVariant.issue_id == int(snap.issue_id))
            .order_by(CatalogVariant.id.asc())
        ).first()

        before_issue = {
            "external_source_ids": dict(issue.external_source_ids or {}),
        }
        fields_updated, upc_id, upc_created = _apply_identity_planned(
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
            continue

        processed += 1
        report.updated_issues += 1
        if upc_created:
            report.inserted_upcs += 1

        gcd_inputs = _normalize_gcd_inputs(gcd_row)
        written = {
            "catalog_issue_id": int(snap.issue_id),
            "gcd_issue_id": int(gcd_inputs["gcd_issue_id"]),
            "fields_updated": fields_updated,
            "inserted_upc": upc_created,
            "barcode": gcd_inputs.get("barcode"),
        }
        if upc_id is not None:
            written["upc_id"] = int(upc_id)
        report.written_rows.append(written)

        if rollback_collector is not None:
            rollback_collector.setdefault("issue_snapshots", []).append(
                {
                    "catalog_issue_id": int(snap.issue_id),
                    "identity_only": True,
                    "before": before_issue,
                }
            )
            if upc_created and upc_id is not None:
                rollback_collector.setdefault("upc_ids", []).append(int(upc_id))

    session.commit()
    report.perf = {"elapsed_sec": round(time.perf_counter() - t0, 3)}
    return report
