"""Read-only analytics over ``comicvine_volume_universe`` (P97-23A)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue
from app.models.catalog_p97 import ComicVineVolumeUniverse


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
class UniverseAnalyticsReport:
    total_discovered_volumes: int
    total_discoverable_issues: int
    current_catalog_issues: int
    projected_comicos_catalog_ceiling: int
    issues_not_yet_in_catalog: int
    largest_volumes: list[UniverseVolumeSizeRow]
    top_publishers: list[UniversePublisherIssueRow]


def _publisher_label(value: str | None) -> str:
    text = (value or "").strip()
    return text or "Unknown"


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

    ceiling = total_issues
    delta = max(0, ceiling - current_catalog)

    return UniverseAnalyticsReport(
        total_discovered_volumes=total_volumes,
        total_discoverable_issues=total_issues,
        current_catalog_issues=current_catalog,
        projected_comicos_catalog_ceiling=ceiling,
        issues_not_yet_in_catalog=delta,
        largest_volumes=largest,
        top_publishers=publishers,
    )
