"""P101 Modern Catalog Acquisition — read-only coverage audit (2009+ focus publishers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import extract, func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)

YearKey = int | Literal["Unknown"]

P101_YEAR_MIN = 2009
P101_YEAR_MAX = 2026

# Canonical report labels → normalized publisher keys (subset of P97 weights).
_FOCUS_PUBLISHER_VARIANTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Marvel", ("marvel", "marvel comics")),
    ("DC", ("dc", "dc comics")),
    ("Image", ("image", "image comics")),
    ("Dark Horse", ("dark horse", "dark horse comics")),
    ("IDW", ("idw", "idw publishing")),
    ("Boom", ("boom", "boom studios", "boom! studios")),
    ("Dynamite", ("dynamite", "dynamite entertainment")),
    ("Valiant", ("valiant", "valiant entertainment", "valiant comics")),
)


def canonical_focus_publisher_label(publisher_name: str | None) -> str | None:
    norm = normalize_series_name(publisher_name or "")
    if not norm:
        return None
    for label, variants in _FOCUS_PUBLISHER_VARIANTS:
        if norm in variants:
            return label
        for variant in variants:
            if norm.startswith(variant) or variant.startswith(norm):
                return label
    return None


def issue_year_key(cover_year: int | None, release_year: int | None) -> YearKey:
    if cover_year is not None:
        return int(cover_year)
    if release_year is not None:
        return int(release_year)
    return "Unknown"


def _in_modern_year_range(year: YearKey) -> bool:
    return isinstance(year, int) and P101_YEAR_MIN <= year <= P101_YEAR_MAX


@dataclass(frozen=True)
class ModernCatalogAuditRow:
    year: YearKey
    publisher: str
    existing_issues: int
    discovered_issues: int
    imported_issues: int
    remaining_gap: int


@dataclass
class ModernCatalogAuditReport:
    report_at: str
    year_min: int
    year_max: int
    focus_publishers: tuple[str, ...]
    mode: str = "audit_only"
    catalog_issue_total: int = 0
    universe_volumes_total: int = 0
    universe_volumes_modern_focus: int = 0
    rows: list[ModernCatalogAuditRow] = field(default_factory=list)
    year_totals_all_publishers: dict[str, int] = field(default_factory=dict)
    modern_focus_totals: dict[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)


def _empty_row(year: YearKey, publisher: str) -> ModernCatalogAuditRow:
    return ModernCatalogAuditRow(
        year=year,
        publisher=publisher,
        existing_issues=0,
        discovered_issues=0,
        imported_issues=0,
        remaining_gap=0,
    )


def _collect_existing_by_publisher_year(session: Session) -> dict[tuple[str, YearKey], int]:
    issue_year = func.coalesce(
        extract("year", CatalogIssue.cover_date),
        extract("year", CatalogIssue.release_date),
    )
    statement = (
        select(CatalogPublisher.name, issue_year, func.count())
        .join(CatalogPublisher, CatalogIssue.publisher_id == CatalogPublisher.id)
        .group_by(CatalogPublisher.name, issue_year)
    )
    out: dict[tuple[str, YearKey], int] = {}
    for pub_name, year_val, count in session.exec(statement).all():
        label = canonical_focus_publisher_label(str(pub_name))
        if label is None:
            continue
        key_year: YearKey = int(year_val) if year_val is not None else "Unknown"
        bucket = (label, key_year)
        out[bucket] = out.get(bucket, 0) + int(count)
    return out


def _collect_year_totals_all_publishers(session: Session) -> dict[str, int]:
    issue_year = func.coalesce(
        extract("year", CatalogIssue.cover_date),
        extract("year", CatalogIssue.release_date),
    )
    statement = select(issue_year, func.count()).select_from(CatalogIssue).group_by(issue_year)
    totals: dict[str, int] = {}
    for year_val, count in session.exec(statement).all():
        label = str(int(year_val)) if year_val is not None else "Unknown"
        totals[label] = totals.get(label, 0) + int(count)
    return dict(sorted(totals.items(), key=lambda item: (item[0] == "Unknown", item[0])))


def _collect_universe_gap_by_publisher_year(
    session: Session,
) -> dict[tuple[str, YearKey], tuple[int, int, int]]:
    """Returns (discovered, existing_in_volume_scope, gap) keyed by focus publisher + volume start_year."""
    indexes = build_catalog_coverage_indexes(session)
    out: dict[tuple[str, YearKey], tuple[int, int, int]] = {}
    for row in session.exec(select(ComicVineVolumeUniverse)).all():
        label = canonical_focus_publisher_label(row.publisher)
        if label is None:
            continue
        start_year = row.start_year
        if start_year is None:
            year_key: YearKey = "Unknown"
        else:
            try:
                year_key = int(start_year)
            except (TypeError, ValueError):
                year_key = "Unknown"
        if not _in_modern_year_range(year_key):
            continue
        count_of_issues = int(row.count_of_issues or 0)
        if count_of_issues <= 0:
            continue
        existing = existing_issue_count_for_volume(
            volume_id=int(row.volume_id),
            name=row.name,
            publisher=row.publisher,
            indexes=indexes,
        )
        existing_capped = min(int(existing), count_of_issues)
        gap = max(count_of_issues - existing_capped, 0)
        key = (label, year_key)
        discovered, existing_sum, gap_sum = out.get(key, (0, 0, 0))
        out[key] = (
            discovered + count_of_issues,
            existing_sum + existing_capped,
            gap_sum + gap,
        )
    return out


def build_modern_catalog_audit_report(session: Session) -> ModernCatalogAuditReport:
    report = ModernCatalogAuditReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        year_min=P101_YEAR_MIN,
        year_max=P101_YEAR_MAX,
        focus_publishers=tuple(label for label, _ in _FOCUS_PUBLISHER_VARIANTS),
    )
    report.catalog_issue_total = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())
    report.universe_volumes_total = int(
        session.exec(select(func.count()).select_from(ComicVineVolumeUniverse)).one()
    )
    report.year_totals_all_publishers = _collect_year_totals_all_publishers(session)

    existing_map = _collect_existing_by_publisher_year(session)
    universe_map = _collect_universe_gap_by_publisher_year(session)

    keys: set[tuple[str, YearKey]] = set()
    for label, year_key in existing_map:
        if _in_modern_year_range(year_key):
            keys.add((label, year_key))
    keys.update(universe_map.keys())

    rows: list[ModernCatalogAuditRow] = []
    for label, year_key in sorted(keys, key=lambda item: (item[1] if isinstance(item[1], int) else 9999, item[0])):
        existing = int(existing_map.get((label, year_key), 0))
        discovered, _existing_scope, gap = universe_map.get((label, year_key), (0, 0, 0))
        rows.append(
            ModernCatalogAuditRow(
                year=year_key,
                publisher=label,
                existing_issues=existing,
                discovered_issues=discovered,
                imported_issues=0,
                remaining_gap=gap,
            )
        )

    report.rows = rows
    report.universe_volumes_modern_focus = len(
        {
            int(row.volume_id)
            for row in session.exec(select(ComicVineVolumeUniverse)).all()
            if canonical_focus_publisher_label(row.publisher) is not None
            and _in_modern_year_range(int(row.start_year) if row.start_year is not None else -1)
        }
    )

    modern_existing = sum(r.existing_issues for r in rows)
    modern_discovered = sum(r.discovered_issues for r in rows)
    modern_gap = sum(r.remaining_gap for r in rows)

    def _sum_issue_years(lo: int, hi: int) -> int:
        total = 0
        for key, count in report.year_totals_all_publishers.items():
            if key.isdigit() and lo <= int(key) <= hi:
                total += int(count)
        return total

    report.modern_focus_totals = {
        "existing_issues_issue_year": modern_existing,
        "discovered_issues_volume_start_year": modern_discovered,
        "remaining_gap_volume_scope": modern_gap,
        "queue_candidate_volumes": report.universe_volumes_modern_focus,
        "all_publishers_issue_years_2009_2026": _sum_issue_years(P101_YEAR_MIN, P101_YEAR_MAX),
        "all_publishers_issue_years_2010_2026": _sum_issue_years(2010, P101_YEAR_MAX),
        "all_publishers_issue_year_unknown": int(report.year_totals_all_publishers.get("Unknown", 0)),
        "all_publishers_issue_year_2008": int(report.year_totals_all_publishers.get("2008", 0)),
    }

    report.notes = (
        "audit_only: imported_issues is always 0 until a live import job runs.",
        "existing_issues uses catalog_issue cover_date, else release_date, grouped by focus publisher.",
        "discovered_issues and remaining_gap use comicvine_volume_universe volumes with "
        f"start_year in {P101_YEAR_MIN}–{P101_YEAR_MAX}; issue counts are ComicVine count_of_issues.",
        "If universe_volumes_total is 0, run p97_discover_comicvine_universe before queue build.",
    )
    return report


def audit_report_to_json(report: ModernCatalogAuditReport) -> dict[str, Any]:
    return {
        "report_at": report.report_at,
        "mode": report.mode,
        "year_min": report.year_min,
        "year_max": report.year_max,
        "focus_publishers": list(report.focus_publishers),
        "catalog_issue_total": report.catalog_issue_total,
        "universe_volumes_total": report.universe_volumes_total,
        "universe_volumes_modern_focus": report.universe_volumes_modern_focus,
        "year_totals_all_publishers": report.year_totals_all_publishers,
        "modern_focus_totals": report.modern_focus_totals,
        "notes": list(report.notes),
        "rows": [
            {
                "year": row.year,
                "publisher": row.publisher,
                "existing_issues": row.existing_issues,
                "discovered_issues": row.discovered_issues,
                "imported_issues": row.imported_issues,
                "remaining_gap": row.remaining_gap,
            }
            for row in report.rows
        ],
    }
