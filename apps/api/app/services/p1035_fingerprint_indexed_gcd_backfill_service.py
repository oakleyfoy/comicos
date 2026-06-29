"""P103.5 — GCD identity backfill scoped to catalog_image_fingerprint rows (GCD id only)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import (
    CatalogImageFingerprint,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
    CatalogUpc,
    CatalogVariant,
)
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.p103_gcd_enrichment_helpers import effective_catalog_issue_year
from app.services.p101_catalog_cache_service import CatalogCacheContext, YEAR_MAX, YEAR_MIN
from app.services.p103_gcd_catalog_enrichment_service import EnrichmentFilters
from app.services.p103_gcd_enrichment_fast import EnrichmentIssueSnapshot, load_gcd_index_for_enrichment
from app.services.p103_gcd_enrichment_helpers import extract_gcd_issue_id
from app.services.p1035_gcd_identity_backfill_service import (
    _apply_identity_planned,
    _cv_duplicate_conflict,
    _expand_scope_for_gcd_index,
    _normalize_gcd_inputs,
    build_comicvine_duplicate_index,
    lookup_gcd_for_catalog,
    plan_identity_backfill,
)
from app.services.p1035_gcd_identity_exception_service import (
    P1035ExceptionCollector,
    explain_ambiguous_gcd_lookup,
    record_ambiguous_match,
    record_duplicate_cv_conflict,
)
from app.services.gcd_catalog_upc_insert_service import preload_catalog_upc_guards
from app.models.intake_queue import ComicIssueBarcode


def _is_comicvine_primary(external: dict[str, Any] | None) -> bool:
    if not isinstance(external, dict):
        return False
    return str(external.get("_primary_source") or "").upper() == "COMICVINE"


def _identity_fields_present(snap: EnrichmentIssueSnapshot) -> bool:
    pub = (snap.publisher_name or "").strip()
    series = (snap.series_name or "").strip()
    title = (snap.title or "").strip()
    issue_num = (snap.issue_number or "").strip()
    if not pub or not issue_num:
        return False
    if not series and not title:
        return False
    return True


def _fingerprint_indexed_issue_ids(session: Session) -> set[int]:
    rows = session.exec(
        select(CatalogImageFingerprint.issue_id).where(CatalogImageFingerprint.issue_id.is_not(None)).distinct()
    ).all()
    return {int(x) for x in rows if x is not None}


def _gcd_coverage_counts(session: Session, issue_ids: set[int]) -> tuple[int, int, int]:
    total = len(issue_ids)
    if total == 0:
        return 0, 0, 0
    with_gcd = 0
    sorted_ids = sorted(issue_ids)
    for chunk_start in range(0, len(sorted_ids), 5000):
        chunk = sorted_ids[chunk_start : chunk_start + 5000]
        rows = session.exec(
            select(CatalogIssue.id, CatalogIssue.external_source_ids).where(CatalogIssue.id.in_(chunk))
        ).all()
        for _iid, ext in rows:
            if extract_gcd_issue_id(ext) is not None:
                with_gcd += 1
    without = total - with_gcd
    return total, with_gcd, without


def _coverage_pct(with_gcd: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * with_gcd / total, 2)


def _snapshot_from_issue_row(
    issue: CatalogIssue,
    *,
    series_by_id: dict[int, CatalogSeries],
    publisher_by_id: dict[int, CatalogPublisher],
    has_upc: set[int],
) -> EnrichmentIssueSnapshot:
    series = series_by_id.get(int(issue.series_id)) if issue.series_id else None
    pub_name: str | None = None
    if issue.publisher_id:
        pub = publisher_by_id.get(int(issue.publisher_id))
        pub_name = pub.name if pub else None
    elif series and series.publisher_id:
        pub = publisher_by_id.get(int(series.publisher_id))
        pub_name = pub.name if pub else None
    year = effective_catalog_issue_year(
        year=None,
        cover_date=issue.cover_date,
        release_date=issue.release_date,
    )
    return EnrichmentIssueSnapshot(
        issue_id=int(issue.id or 0),
        year=year,
        publisher_id=int(issue.publisher_id) if issue.publisher_id else None,
        series_id=int(issue.series_id) if issue.series_id else None,
        publisher_norm=normalize_series_name(pub_name or ""),
        series_norm=normalize_series_name(series.name if series else ""),
        issue_norm=normalize_issue_number(issue.normalized_issue_number or issue.issue_number or ""),
        publisher_name=pub_name,
        series_name=series.name if series else None,
        issue_number=issue.issue_number,
        cover_date=issue.cover_date,
        release_date=issue.release_date,
        store_date=issue.store_date,
        title=issue.title,
        description=issue.description,
        external_source_ids=dict(issue.external_source_ids or {}),
        variant_printing=None,
        variant_variant_name=None,
        has_upc=int(issue.id or 0) in has_upc,
    )


def _load_fingerprint_backfill_snapshots(
    session: Session,
    issue_ids: set[int],
) -> list[EnrichmentIssueSnapshot]:
    if not issue_ids:
        return []
    sorted_ids = sorted(issue_ids)
    issues: list[CatalogIssue] = []
    for chunk_start in range(0, len(sorted_ids), 5000):
        chunk = sorted_ids[chunk_start : chunk_start + 5000]
        issues.extend(session.exec(select(CatalogIssue).where(CatalogIssue.id.in_(chunk))).all())

    missing = [issue for issue in issues if extract_gcd_issue_id(issue.external_source_ids) is None]
    if not missing:
        return []

    series_ids = {int(i.series_id) for i in missing if i.series_id}
    publisher_ids = {int(i.publisher_id) for i in missing if i.publisher_id}
    series_by_id: dict[int, CatalogSeries] = {}
    if series_ids:
        sid_list = sorted(series_ids)
        for chunk_start in range(0, len(sid_list), 5000):
            chunk = sid_list[chunk_start : chunk_start + 5000]
            for row in session.exec(select(CatalogSeries).where(CatalogSeries.id.in_(chunk))).all():
                if row.id is not None:
                    series_by_id[int(row.id)] = row
                    if row.publisher_id:
                        publisher_ids.add(int(row.publisher_id))
    publisher_by_id: dict[int, CatalogPublisher] = {}
    if publisher_ids:
        pid_list = sorted(publisher_ids)
        for chunk_start in range(0, len(pid_list), 5000):
            chunk = pid_list[chunk_start : chunk_start + 5000]
            for row in session.exec(select(CatalogPublisher).where(CatalogPublisher.id.in_(chunk))).all():
                if row.id is not None:
                    publisher_by_id[int(row.id)] = row

    missing_ids = [int(i.id or 0) for i in missing if i.id is not None]
    has_upc: set[int] = set()
    for chunk_start in range(0, len(missing_ids), 5000):
        chunk = missing_ids[chunk_start : chunk_start + 5000]
        for row in session.exec(select(CatalogUpc.issue_id).where(CatalogUpc.issue_id.in_(chunk))).all():
            if row is not None:
                has_upc.add(int(row))

    snaps = [
        _snapshot_from_issue_row(
            issue,
            series_by_id=series_by_id,
            publisher_by_id=publisher_by_id,
            has_upc=has_upc,
        )
        for issue in missing
    ]
    snaps.sort(
        key=lambda s: (
            0 if _is_comicvine_primary(s.external_source_ids) else 1,
            int(s.issue_id),
        )
    )
    return snaps


def _identity_only_planned(planned: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [p for p in planned if str(p.get("field") or "").startswith("external_source_ids")]


@dataclass
class FingerprintIndexedGcdBackfillReport:
    mode: str = "fingerprint_indexed_gcd_backfill"
    dry_run: bool = True
    report_at: str = ""
    gcd_database: str = ""
    elapsed_seconds: float = 0.0
    limit: int | None = None
    total_fingerprint_indexed: int = 0
    with_gcd_before: int = 0
    without_gcd_before: int = 0
    coverage_pct_before: float = 0.0
    eligible_missing_gcd: int = 0
    skipped_incomplete_identity: int = 0
    attempted: int = 0
    matched: int = 0
    written_gcd_links: int = 0
    skipped_ambiguous: int = 0
    skipped_no_match: int = 0
    skipped_duplicate_cv: int = 0
    skipped_plan_conflicts: int = 0
    with_gcd_after: int = 0
    coverage_pct_after: float = 0.0
    sample_matches: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_review_path: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "dry_run": self.dry_run,
            "report_at": self.report_at,
            "gcd_database": self.gcd_database,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "limit": self.limit,
            "total_fingerprint_indexed": self.total_fingerprint_indexed,
            "with_gcd_before": self.with_gcd_before,
            "without_gcd_before": self.without_gcd_before,
            "coverage_pct_before": self.coverage_pct_before,
            "eligible_missing_gcd": self.eligible_missing_gcd,
            "skipped_incomplete_identity": self.skipped_incomplete_identity,
            "attempted": self.attempted,
            "matched": self.matched,
            "written_gcd_links": self.written_gcd_links,
            "skipped_ambiguous": self.skipped_ambiguous,
            "skipped_no_match": self.skipped_no_match,
            "skipped_duplicate_cv": self.skipped_duplicate_cv,
            "skipped_plan_conflicts": self.skipped_plan_conflicts,
            "with_gcd_after": self.with_gcd_after,
            "coverage_pct_after": self.coverage_pct_after,
            "sample_matches": self.sample_matches,
            "ambiguous_review_path": self.ambiguous_review_path,
        }


def run_fingerprint_indexed_gcd_backfill(
    session: Session,
    *,
    gcd_path: Path,
    cache_path: Path,
    dry_run: bool = True,
    limit: int | None = None,
    ambiguous_log_path: Path | None = None,
) -> FingerprintIndexedGcdBackfillReport:
    t0 = time.perf_counter()
    report = FingerprintIndexedGcdBackfillReport(
        dry_run=dry_run,
        report_at=datetime.now(timezone.utc).isoformat(),
        gcd_database=str(gcd_path),
        limit=limit,
    )

    fp_ids = _fingerprint_indexed_issue_ids(session)
    total, with_before, without_before = _gcd_coverage_counts(session, fp_ids)
    report.total_fingerprint_indexed = total
    report.with_gcd_before = with_before
    report.without_gcd_before = without_before
    report.coverage_pct_before = _coverage_pct(with_before, total)

    all_snaps = _load_fingerprint_backfill_snapshots(session, fp_ids)
    eligible: list[EnrichmentIssueSnapshot] = []
    for snap in all_snaps:
        if _identity_fields_present(snap):
            eligible.append(snap)
        else:
            report.skipped_incomplete_identity += 1
    report.eligible_missing_gcd = len(eligible)

    ctx = CatalogCacheContext.load(cache_path)
    dup_index = build_comicvine_duplicate_index(eligible)
    scope_by_id = {int(s.issue_id): s for s in eligible}
    expanded = _expand_scope_for_gcd_index(eligible)
    filters = EnrichmentFilters(
        publisher=None,
        year_from=YEAR_MIN,
        year_to=YEAR_MAX,
        limit=limit,
        all_catalog=True,
        year_filter_explicit=False,
    )
    gcd_index = load_gcd_index_for_enrichment(
        gcd_path,
        year_from=filters.year_from,
        year_to=filters.year_to,
        focus_publisher=filters.publisher,
        all_catalog=filters.all_catalog,
        year_filter_explicit=filters.year_filter_explicit,
        catalog_scope=expanded,
    )

    collector = P1035ExceptionCollector()
    learned = {str(b) for b in session.exec(select(ComicIssueBarcode.normalized_barcode)).all() if b}
    upc_map, upc_id_by_normalized = preload_catalog_upc_guards(session)

    processed_writes = 0
    for snap in eligible:
        if limit is not None and report.attempted >= limit:
            break
        report.attempted += 1

        if _cv_duplicate_conflict(snap, dup_index):
            report.skipped_duplicate_cv += 1
            record_duplicate_cv_conflict(
                collector, snap=snap, dup_index=dup_index, scope_by_id=scope_by_id
            )
            continue

        gcd_row = lookup_gcd_for_catalog(gcd_index, snap)
        if gcd_row is None:
            reason, _candidates = explain_ambiguous_gcd_lookup(gcd_index, snap)
            if reason == "no_gcd_match":
                report.skipped_no_match += 1
            else:
                report.skipped_ambiguous += 1
                record_ambiguous_match(collector, snap=snap, index=gcd_index, ctx=ctx)
            continue

        planned, skip, _upc_n = plan_identity_backfill(snap, gcd_row, ctx=ctx)
        planned = _identity_only_planned(planned)
        if skip in ("learned_barcode_conflict", "upc_mapped_elsewhere"):
            report.skipped_plan_conflicts += 1
            continue
        if not planned:
            if skip:
                report.skipped_plan_conflicts += 1
            continue

        report.matched += 1
        gcd_inputs = _normalize_gcd_inputs(gcd_row)
        if len(report.sample_matches) < 25:
            report.sample_matches.append(
                {
                    "catalog_issue_id": int(snap.issue_id),
                    "series": snap.series_name,
                    "issue_number": snap.issue_number,
                    "publisher": snap.publisher_name,
                    "gcd_issue_id": gcd_inputs.get("gcd_issue_id"),
                    "comicvine_primary": _is_comicvine_primary(snap.external_source_ids),
                }
            )

        if dry_run:
            report.written_gcd_links += 1
            continue

        issue = session.get(CatalogIssue, int(snap.issue_id))
        if issue is None:
            continue
        if extract_gcd_issue_id(issue.external_source_ids) is not None:
            continue
        variant = session.exec(
            select(CatalogVariant)
            .where(CatalogVariant.issue_id == int(snap.issue_id))
            .order_by(CatalogVariant.id.asc())
        ).first()
        fields_updated, _upc_id, _upc_created = _apply_identity_planned(
            session,
            issue,
            variant,
            planned,
            learned=learned,
            upc_map=upc_map,
            upc_id_by_normalized=upc_id_by_normalized,
        )
        if fields_updated > 0:
            processed_writes += 1
            report.written_gcd_links += 1

    if not dry_run and processed_writes > 0:
        session.commit()

    if dry_run:
        report.with_gcd_after = with_before + report.written_gcd_links
    else:
        _, with_after, _ = _gcd_coverage_counts(session, fp_ids)
        report.with_gcd_after = with_after
    report.coverage_pct_after = _coverage_pct(report.with_gcd_after, total)

    if ambiguous_log_path is not None and (
        collector.ambiguous_matches or collector.duplicate_cv_conflicts
    ):
        ambiguous_log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "report_at": report.report_at,
            "ambiguous_matches": collector.ambiguous_matches,
            "duplicate_cv_conflicts": collector.duplicate_cv_conflicts,
        }
        ambiguous_log_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        report.ambiguous_review_path = str(ambiguous_log_path)

    report.elapsed_seconds = time.perf_counter() - t0
    return report


def format_fingerprint_indexed_gcd_backfill_report(report: FingerprintIndexedGcdBackfillReport) -> str:
    lines = [
        "=" * 72,
        f"P103.5 fingerprint-indexed GCD backfill ({'DRY-RUN' if report.dry_run else 'WRITE'})",
        "=" * 72,
        f"total_fingerprint_indexed: {report.total_fingerprint_indexed:,}",
        f"with_gcd_before: {report.with_gcd_before:,}",
        f"without_gcd_before: {report.without_gcd_before:,}",
        f"coverage_pct_before: {report.coverage_pct_before}%",
        f"eligible_missing_gcd: {report.eligible_missing_gcd:,}",
        f"skipped_incomplete_identity: {report.skipped_incomplete_identity:,}",
        f"attempted: {report.attempted:,}",
        f"matched: {report.matched:,}",
        f"written_gcd_links: {report.written_gcd_links:,}",
        f"skipped_ambiguous: {report.skipped_ambiguous:,}",
        f"skipped_no_match: {report.skipped_no_match:,}",
        f"skipped_duplicate_cv: {report.skipped_duplicate_cv:,}",
        f"skipped_plan_conflicts: {report.skipped_plan_conflicts:,}",
        f"with_gcd_after: {report.with_gcd_after:,}",
        f"coverage_pct_after: {report.coverage_pct_after}%",
        f"elapsed_seconds: {report.elapsed_seconds:.1f}",
    ]
    if report.ambiguous_review_path:
        lines.append(f"ambiguous_review_path: {report.ambiguous_review_path}")
    lines.append("=" * 72)
    return "\n".join(lines)
