"""P101-B — GCD vs ComicVine vs ComicOS coverage comparison (read-only).

Compares issue-level keys (publisher + series + issue number) for modern years.
ComicVine per-issue shells are used when ``universe_issue`` is populated; otherwise
volume metadata from ``comicvine_volume_universe`` supplies totals and a volume-level
heuristic for whether ComicVine likely lists an issue number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, func, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    series_names_compatible,
)
from app.services.gcd_barcode_import_service import _year_from_key_date
from app.services.p101_modern_catalog_audit_service import issue_year_key
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)

YearKey = int | Literal["Unknown"]
P101B_YEAR_MIN = 2009
P101B_YEAR_MAX = 2026
P101B_YEARS: tuple[int, ...] = tuple(range(P101B_YEAR_MIN, P101B_YEAR_MAX + 1))

IssueKey = tuple[str, str, str]  # publisher_norm, series_norm, issue_norm


@dataclass
class YearBucket:
    year: YearKey
    comicos_issues: int = 0
    gcd_issues: int = 0
    comicvine_issues: int = 0
    missing_from_comicos_in_gcd: int = 0
    missing_from_comicos_in_comicvine: int = 0
    present_in_gcd_and_comicvine: int = 0
    present_only_in_gcd: int = 0
    present_only_in_comicvine: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "comicos_issues": self.comicos_issues,
            "gcd_issues": self.gcd_issues,
            "comicvine_issues": self.comicvine_issues,
            "missing_from_comicos_in_gcd": self.missing_from_comicos_in_gcd,
            "missing_from_comicos_in_comicvine": self.missing_from_comicos_in_comicvine,
            "present_in_gcd_and_comicvine": self.present_in_gcd_and_comicvine,
            "present_only_in_gcd": self.present_only_in_gcd,
            "present_only_in_comicvine": self.present_only_in_comicvine,
        }


@dataclass
class P101GcdCoverageReport:
    report_at: str
    gcd_db: str | None
    totals: YearBucket
    by_year: dict[str, YearBucket] = field(default_factory=dict)
    universe_issue_rows: int = 0
    comicvine_volume_rows: int = 0
    comicvine_volume_gap_issues: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, Any]:
        return {
            "report_at": self.report_at,
            "gcd_db": self.gcd_db,
            "year_min": P101B_YEAR_MIN,
            "year_max": P101B_YEAR_MAX,
            "totals": self.totals.as_dict(),
            "by_year": {k: v.as_dict() for k, v in self.by_year.items()},
            "universe_issue_rows": self.universe_issue_rows,
            "comicvine_volume_rows": self.comicvine_volume_rows,
            "comicvine_volume_gap_issues": self.comicvine_volume_gap_issues,
            "notes": list(self.notes),
        }


def _issue_key(publisher: str | None, series: str | None, issue_number: str | None) -> IssueKey | None:
    pub = normalize_series_name(publisher or "")
    series_norm = normalize_series_name(series or "")
    issue_norm = normalize_issue_number(issue_number or "")
    if not pub or not series_norm or not issue_norm:
        return None
    return (pub, series_norm, issue_norm)


def _year_in_scope(year: YearKey) -> bool:
    return isinstance(year, int) and P101B_YEAR_MIN <= year <= P101B_YEAR_MAX


def _issue_int(issue_norm: str) -> int | None:
    try:
        return int(issue_norm)
    except (TypeError, ValueError):
        return None


@dataclass
class _CvVolumeRef:
    volume_id: int
    name: str
    publisher: str | None
    start_year: int | None
    count_of_issues: int


def _build_comicvine_volume_index(session: Session) -> list[_CvVolumeRef]:
    return [
        _CvVolumeRef(
            volume_id=int(row.volume_id),
            name=str(row.name or ""),
            publisher=row.publisher,
            start_year=int(row.start_year) if row.start_year is not None else None,
            count_of_issues=int(row.count_of_issues or 0),
        )
        for row in session.exec(select(ComicVineVolumeUniverse)).all()
        if int(row.count_of_issues or 0) > 0
    ]


def _comicvine_has_issue(
    volumes: list[_CvVolumeRef],
    *,
    publisher_norm: str,
    series_norm: str,
    issue_norm: str,
) -> bool:
    issue_n = _issue_int(issue_norm)
    for vol in volumes:
        pub_ok = normalize_series_name(vol.publisher or "") == publisher_norm or series_names_compatible(
            publisher_norm, normalize_series_name(vol.publisher or "")
        )
        if not pub_ok:
            continue
        vol_series = normalize_series_name(vol.name)
        if vol_series != series_norm and not series_names_compatible(series_norm, vol_series):
            continue
        if issue_n is None:
            return True
        if 1 <= issue_n <= int(vol.count_of_issues):
            return True
    return False


def _load_catalog_keys(session: Session) -> tuple[dict[IssueKey, YearKey], dict[YearKey, int]]:
    pubs = {int(pid): name for pid, name in session.exec(select(CatalogPublisher.id, CatalogPublisher.name)).all() if pid}
    series_meta = {
        int(sid): (name, pub_id)
        for sid, name, pub_id in session.exec(select(CatalogSeries.id, CatalogSeries.name, CatalogSeries.publisher_id)).all()
        if sid is not None
    }
    keys: dict[IssueKey, YearKey] = {}
    year_counts: dict[YearKey, int] = {}
    rows = session.exec(
        select(
            CatalogIssue.series_id,
            CatalogIssue.issue_number,
            CatalogIssue.normalized_issue_number,
            CatalogIssue.cover_date,
            CatalogIssue.release_date,
        )
    ).all()
    for series_id, issue_number, norm_issue, cover_date, release_date in rows:
        if series_id is None:
            continue
        series_name, pub_id = series_meta.get(int(series_id), ("", None))
        pub_name = pubs.get(int(pub_id), "") if pub_id else ""
        key = _issue_key(pub_name, series_name, norm_issue or issue_number)
        if key is None:
            continue
        year = issue_year_key(
            cover_date.year if cover_date is not None else None,
            release_date.year if release_date is not None else None,
        )
        keys[key] = year
        year_counts[year] = year_counts.get(year, 0) + 1
    return keys, year_counts


def _load_gcd_keys(gcd: Engine | None) -> tuple[dict[IssueKey, YearKey], dict[YearKey, int], int]:
    if gcd is None:
        return {}, {}, 0
    query = text(
        """
        SELECT p.name AS publisher_name, s.name AS series_name, i.number AS number,
               i.key_date AS key_date, s.year_began AS year_began
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        """
    )
    keys: dict[IssueKey, YearKey] = {}
    year_counts: dict[YearKey, int] = {}
    total = 0
    with gcd.connect() as conn:
        total = int(conn.execute(text("SELECT COUNT(*) FROM gcd_issue")).scalar() or 0)
        for row in conn.execute(query):
            key = _issue_key(row.publisher_name, row.series_name, row.number)
            if key is None:
                continue
            year_val = _year_from_key_date(row.key_date, row.year_began)
            year: YearKey = int(year_val) if year_val is not None else "Unknown"
            keys[key] = year
            year_counts[year] = year_counts.get(year, 0) + 1
    return keys, year_counts, total


def _comicvine_issue_totals_by_year(volumes: list[_CvVolumeRef]) -> dict[YearKey, int]:
    out: dict[YearKey, int] = {}
    for vol in volumes:
        year: YearKey = int(vol.start_year) if vol.start_year is not None else "Unknown"
        out[year] = out.get(year, 0) + int(vol.count_of_issues)
    return out


def _volume_gap_by_year(session: Session, volumes: list[_CvVolumeRef]) -> dict[YearKey, int]:
    indexes = build_catalog_coverage_indexes(session)
    out: dict[YearKey, int] = {}
    for vol in volumes:
        year: YearKey = int(vol.start_year) if vol.start_year is not None else "Unknown"
        existing = existing_issue_count_for_volume(
            volume_id=vol.volume_id,
            name=vol.name,
            publisher=vol.publisher,
            indexes=indexes,
        )
        gap = max(int(vol.count_of_issues) - min(int(existing), int(vol.count_of_issues)), 0)
        if gap <= 0:
            continue
        out[year] = out.get(year, 0) + gap
    return out


def _empty_buckets() -> dict[str, YearBucket]:
    buckets: dict[str, YearBucket] = {}
    for year in P101B_YEARS:
        buckets[str(year)] = YearBucket(year=year)
    buckets["Unknown"] = YearBucket(year="Unknown")
    return buckets


def build_p101_gcd_coverage_report(
    session: Session,
    *,
    gcd: Engine | None = None,
    gcd_db: str | None = None,
) -> P101GcdCoverageReport:
    report = P101GcdCoverageReport(
        report_at=datetime.now(timezone.utc).isoformat(),
        gcd_db=gcd_db,
        totals=YearBucket(year="Unknown"),
    )
    by_year = _empty_buckets()

    catalog_keys, catalog_year_counts = _load_catalog_keys(session)
    gcd_keys, gcd_year_counts, gcd_total_all = _load_gcd_keys(gcd)
    cv_volumes = _build_comicvine_volume_index(session)
    cv_year_totals = _comicvine_issue_totals_by_year(cv_volumes)
    cv_gap_by_year = _volume_gap_by_year(session, cv_volumes)

    report.comicvine_volume_rows = len(cv_volumes)
    report.comicvine_volume_gap_issues = sum(cv_gap_by_year.values())
    report.universe_issue_rows = int(session.exec(select(func.count()).select_from(UniverseIssue)).one())

    catalog_keys_modern = {k: y for k, y in catalog_keys.items() if _year_in_scope(y)}
    gcd_keys_modern = {k: y for k, y in gcd_keys.items() if _year_in_scope(y)}

    report.totals.comicos_issues = len(catalog_keys)
    report.totals.gcd_issues = gcd_total_all if gcd is not None else 0
    report.totals.comicvine_issues = sum(int(v.count_of_issues) for v in cv_volumes)

    for year in P101B_YEARS:
        yk: YearKey = year
        label = str(year)
        bucket = by_year[label]
        bucket.comicos_issues = sum(1 for y in catalog_keys.values() if y == yk)
        bucket.gcd_issues = gcd_year_counts.get(yk, 0)
        bucket.comicvine_issues = cv_year_totals.get(yk, 0)

    by_year["Unknown"].comicos_issues = catalog_year_counts.get("Unknown", 0)
    by_year["Unknown"].gcd_issues = gcd_year_counts.get("Unknown", 0)
    by_year["Unknown"].comicvine_issues = cv_year_totals.get("Unknown", 0)

    missing_gcd = [k for k in gcd_keys_modern if k not in catalog_keys]
    for key in missing_gcd:
        year = gcd_keys_modern[key]
        if not _year_in_scope(year):
            continue
        in_cv = _comicvine_has_issue(
            cv_volumes,
            publisher_norm=key[0],
            series_norm=key[1],
            issue_norm=key[2],
        )
        report.totals.missing_from_comicos_in_gcd += 1
        if in_cv:
            report.totals.present_in_gcd_and_comicvine += 1
        else:
            report.totals.present_only_in_gcd += 1
        label = str(year)
        bucket = by_year[label]
        bucket.missing_from_comicos_in_gcd += 1
        if in_cv:
            bucket.present_in_gcd_and_comicvine += 1
        else:
            bucket.present_only_in_gcd += 1

    for year, gap in cv_gap_by_year.items():
        if not _year_in_scope(year):
            continue
        report.totals.missing_from_comicos_in_comicvine += int(gap)
        by_year[str(year)].missing_from_comicos_in_comicvine = int(gap)

    # ComicVine gap issues not explained by a matching GCD key (volume-level remainder).
    gcd_missing_in_cv_gap = max(
        report.totals.missing_from_comicos_in_comicvine - report.totals.present_in_gcd_and_comicvine,
        0,
    )
    report.totals.present_only_in_comicvine = gcd_missing_in_cv_gap
    for year in P101B_YEARS:
        label = str(year)
        gap = by_year[label].missing_from_comicos_in_comicvine
        both = by_year[label].present_in_gcd_and_comicvine
        by_year[label].present_only_in_comicvine = max(gap - both, 0)

    report.by_year = by_year
    notes = [
        "Issue match key: normalized publisher + series + issue number.",
        f"Modern scope for GCD overlap: cover/key year {P101B_YEAR_MIN}–{P101B_YEAR_MAX}.",
        "ComicVine issue totals use comicvine_volume_universe count_of_issues (volume start_year bucket).",
        "ComicVine missing-from-ComicOS uses volume gap (CV count minus catalog count on matched volume).",
        "ComicVine per-issue presence for GCD rows uses volume metadata heuristic (issue # within count_of_issues).",
    ]
    if gcd is None:
        notes = (
            "GCD database not loaded — GCD totals and GCD overlap metrics are zero.",
            *notes,
        )
    if report.universe_issue_rows == 0:
        notes = (
            *notes,
            "universe_issue is empty; ComicVine comparison is volume-metadata based, not per-issue shells.",
        )
    report.notes = tuple(notes)
    return report
