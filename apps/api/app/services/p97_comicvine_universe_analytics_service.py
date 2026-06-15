"""Read-only analytics over ``comicvine_volume_universe`` (P97-23A)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series


@dataclass(frozen=True)
class UniverseVolumeSizeRow:
    volume_id: int
    name: str
    publisher: str | None
    count_of_issues: int


@dataclass(frozen=True)
class UniversePublisherIssueRow:
    publisher: str
    volume_count: int
    total_issues: int


@dataclass(frozen=True)
class UniverseCoverageTotals:
    direct_cv_linked_existing_issues: int
    estimated_matched_existing_issues: int
    issues_not_yet_in_catalog: int
    coverage_percent: float


@dataclass(frozen=True)
class UniverseAnalyticsReport:
    total_discovered_volumes: int
    total_discoverable_issues: int
    current_catalog_issues: int
    projected_comicos_catalog_ceiling: int
    issues_not_yet_in_catalog: int
    direct_cv_linked_existing_issues: int
    estimated_matched_existing_issues: int
    unmatched_discovered_issue_ceiling: int
    coverage_percent: float
    largest_volumes: list[UniverseVolumeSizeRow]
    top_publishers: list[UniversePublisherIssueRow]


def _publisher_label(value: str | None) -> str:
    text = (value or "").strip()
    return text or "Unknown"


def _canonical_series_publisher_key(series_name: str | None, publisher: str | None) -> tuple[str, str]:
    return (
        normalize_series_name(series_name or ""),
        normalize_series_name(_publisher_label(publisher)),
    )


@dataclass(frozen=True)
class CatalogCoverageIndexes:
    direct_by_volume: dict[int, int]
    fallback_by_key: dict[tuple[str, str], int]


@dataclass(frozen=True)
class VolumeCoverageSnapshot:
    volume_id: int
    name: str
    publisher: str | None
    count_of_issues: int
    existing_issue_count: int
    missing_issue_count: int
    coverage_percent: float


def build_catalog_coverage_indexes(session: Session) -> CatalogCoverageIndexes:
    issue_counts_by_series: dict[int, int] = {
        int(series_id): int(count)
        for series_id, count in session.exec(
            select(CatalogIssue.series_id, func.count()).group_by(CatalogIssue.series_id)
        ).all()
        if series_id is not None
    }

    publishers = session.exec(select(CatalogPublisher)).all()
    publisher_name_by_id = {int(row.id): row.name for row in publishers if row.id is not None}

    direct_by_volume: dict[int, int] = {}
    fallback_by_key: dict[tuple[str, str], int] = {}
    for series in session.exec(select(CatalogSeries)).all():
        if series.id is None:
            continue
        issue_count = issue_counts_by_series.get(int(series.id), 0)
        if issue_count <= 0:
            continue
        volume_key = comicvine_volume_id_for_series(series)
        if volume_key:
            try:
                volume_id = int(volume_key)
            except (TypeError, ValueError):
                volume_id = None
            if volume_id is not None:
                direct_by_volume[volume_id] = direct_by_volume.get(volume_id, 0) + issue_count
        pub_name = publisher_name_by_id.get(int(series.publisher_id or 0), "")
        key = (series.normalized_name, normalize_series_name(pub_name))
        fallback_by_key[key] = fallback_by_key.get(key, 0) + issue_count

    return CatalogCoverageIndexes(direct_by_volume=direct_by_volume, fallback_by_key=fallback_by_key)


def existing_issue_count_for_volume(
    *,
    volume_id: int,
    name: str | None,
    publisher: str | None,
    indexes: CatalogCoverageIndexes,
) -> int:
    direct_existing = int(indexes.direct_by_volume.get(int(volume_id), 0))
    if direct_existing > 0:
        return direct_existing
    return int(indexes.fallback_by_key.get(_canonical_series_publisher_key(name, publisher), 0))


def volume_coverage_percent(*, count_of_issues: int, existing_issue_count: int) -> float:
    issue_count = int(count_of_issues)
    if issue_count <= 0:
        return 100.0
    covered = min(int(existing_issue_count), issue_count)
    return round(100.0 * covered / float(issue_count), 1)


def iter_universe_volume_coverage(session: Session) -> list[VolumeCoverageSnapshot]:
    indexes = build_catalog_coverage_indexes(session)
    snapshots: list[VolumeCoverageSnapshot] = []
    for row in session.exec(select(ComicVineVolumeUniverse)).all():
        count_of_issues = int(row.count_of_issues or 0)
        existing = existing_issue_count_for_volume(
            volume_id=int(row.volume_id),
            name=row.name,
            publisher=row.publisher,
            indexes=indexes,
        )
        missing = max(count_of_issues - existing, 0)
        snapshots.append(
            VolumeCoverageSnapshot(
                volume_id=int(row.volume_id),
                name=row.name,
                publisher=row.publisher,
                count_of_issues=count_of_issues,
                existing_issue_count=existing,
                missing_issue_count=missing,
                coverage_percent=volume_coverage_percent(
                    count_of_issues=count_of_issues,
                    existing_issue_count=existing,
                ),
            )
        )
    return snapshots


def compute_universe_catalog_coverage(session: Session) -> UniverseCoverageTotals:
    """Per discovered volume: missing = max(CV issue count - catalog existing, 0)."""
    indexes = build_catalog_coverage_indexes(session)
    universe_rows = session.exec(select(ComicVineVolumeUniverse)).all()
    direct_total = 0
    estimated_total = 0
    missing_total = 0
    discoverable_total = 0
    covered_total = 0

    for row in universe_rows:
        issue_count = int(row.count_of_issues or 0)
        if issue_count <= 0:
            continue
        discoverable_total += issue_count
        direct_existing = int(indexes.direct_by_volume.get(int(row.volume_id), 0))
        if direct_existing > 0:
            existing_count = direct_existing
            direct_total += direct_existing
        else:
            existing_count = int(
                indexes.fallback_by_key.get(_canonical_series_publisher_key(row.name, row.publisher), 0)
            )
            estimated_total += existing_count
        missing = max(issue_count - existing_count, 0)
        missing_total += missing
        covered_total += issue_count - missing

    coverage_percent = (
        round(100.0 * covered_total / float(discoverable_total), 1) if discoverable_total else 0.0
    )
    return UniverseCoverageTotals(
        direct_cv_linked_existing_issues=direct_total,
        estimated_matched_existing_issues=estimated_total,
        issues_not_yet_in_catalog=missing_total,
        coverage_percent=coverage_percent,
    )


def get_universe_analytics_report(
    session: Session,
    *,
    top_volumes_limit: int = 1000,
    top_publishers_limit: int = 100,
) -> UniverseAnalyticsReport:
    total_volumes = int(
        session.exec(select(func.count()).select_from(ComicVineVolumeUniverse)).one()
    )
    total_issues = int(
        session.exec(
            select(func.coalesce(func.sum(ComicVineVolumeUniverse.count_of_issues), 0))
        ).one()
    )
    current_catalog = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())
    coverage = compute_universe_catalog_coverage(session)

    largest_rows = session.exec(
        select(ComicVineVolumeUniverse)
        .where(ComicVineVolumeUniverse.count_of_issues.is_not(None))
        .order_by(ComicVineVolumeUniverse.count_of_issues.desc(), ComicVineVolumeUniverse.volume_id.asc())
        .limit(max(1, int(top_volumes_limit)))
    ).all()
    largest = [
        UniverseVolumeSizeRow(
            volume_id=int(row.volume_id),
            name=row.name,
            publisher=row.publisher,
            count_of_issues=int(row.count_of_issues or 0),
        )
        for row in largest_rows
    ]

    pub_rows = session.exec(
        select(
            ComicVineVolumeUniverse.publisher,
            func.count(),
            func.coalesce(func.sum(ComicVineVolumeUniverse.count_of_issues), 0),
        ).group_by(ComicVineVolumeUniverse.publisher)
    ).all()
    publishers: list[UniversePublisherIssueRow] = []
    for publisher, volume_count, issue_sum in pub_rows:
        publishers.append(
            UniversePublisherIssueRow(
                publisher=_publisher_label(publisher),
                volume_count=int(volume_count),
                total_issues=int(issue_sum),
            )
        )
    publishers.sort(key=lambda row: (-row.total_issues, row.publisher))
    publishers = publishers[: max(1, int(top_publishers_limit))]

    return UniverseAnalyticsReport(
        total_discovered_volumes=total_volumes,
        total_discoverable_issues=total_issues,
        current_catalog_issues=current_catalog,
        projected_comicos_catalog_ceiling=total_issues,
        issues_not_yet_in_catalog=coverage.issues_not_yet_in_catalog,
        direct_cv_linked_existing_issues=coverage.direct_cv_linked_existing_issues,
        estimated_matched_existing_issues=coverage.estimated_matched_existing_issues,
        unmatched_discovered_issue_ceiling=coverage.issues_not_yet_in_catalog,
        coverage_percent=coverage.coverage_percent,
        largest_volumes=largest,
        top_publishers=publishers,
    )
