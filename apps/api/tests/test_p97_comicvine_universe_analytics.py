from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"
for _p in (str(API_ROOT), str(SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.models  # noqa: F401,E402

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries  # noqa: E402
from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.services.catalog_ingestion_service import normalize_series_name  # noqa: E402
from app.services.p97_comicvine_universe_analytics_service import (  # noqa: E402
    compute_universe_catalog_coverage,
    get_universe_analytics_report,
)
import p97_universe_analytics_report as universe_report  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_universe(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=1,
            name="Huge",
            publisher="Marvel",
            count_of_issues=1000,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=2,
            name="Small",
            publisher="DC",
            count_of_issues=5,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=3,
            name="Mid Marvel",
            publisher="Marvel",
            count_of_issues=100,
        )
    )
    session.commit()


def _add_issues(session: Session, series: CatalogSeries, count: int) -> None:
    for i in range(count):
        num = str(i + 1)
        session.add(
            CatalogIssue(series_id=series.id, issue_number=num, normalized_issue_number=num)
        )
    session.commit()


def test_universe_analytics_totals_and_sorting(session: Session) -> None:
    _seed_universe(session)
    report = get_universe_analytics_report(session, top_volumes_limit=10, top_publishers_limit=5)
    assert report.total_discovered_volumes == 3
    assert report.total_discoverable_issues == 1105
    assert report.issues_not_yet_in_catalog == 1105
    assert report.unmatched_discovered_issue_ceiling == 1105
    assert report.coverage_percent == 0.0
    assert [row.volume_id for row in report.largest_volumes] == [1, 3, 2]
    assert report.top_publishers[0].publisher == "Marvel"
    assert report.top_publishers[0].total_issues == 1100


def test_coverage_direct_comicvine_volume_link(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    series = CatalogSeries(
        name="Amazing Spider-Man",
        normalized_name=normalize_series_name("Amazing Spider-Man"),
        publisher_id=pub.id,
        external_source_ids={"COMICVINE": {"87154": "volume"}},
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    _add_issues(session, series, 40)

    session.add(
        ComicVineVolumeUniverse(
            volume_id=87154,
            name="Amazing Spider-Man",
            publisher="Marvel",
            count_of_issues=100,
        )
    )
    session.commit()

    coverage = compute_universe_catalog_coverage(session)
    assert coverage.direct_cv_linked_existing_issues == 40
    assert coverage.estimated_matched_existing_issues == 0
    assert coverage.issues_not_yet_in_catalog == 60
    assert coverage.coverage_percent == pytest.approx(40.0)


def test_coverage_fallback_series_publisher_match(session: Session) -> None:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    series = CatalogSeries(
        name="Huge",
        normalized_name=normalize_series_name("Huge"),
        publisher_id=pub.id,
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    _add_issues(session, series, 250)

    session.add(
        ComicVineVolumeUniverse(
            volume_id=99999,
            name="Huge",
            publisher="Marvel",
            count_of_issues=1000,
        )
    )
    session.commit()

    coverage = compute_universe_catalog_coverage(session)
    assert coverage.direct_cv_linked_existing_issues == 0
    assert coverage.estimated_matched_existing_issues == 250
    assert coverage.issues_not_yet_in_catalog == 750
    assert coverage.coverage_percent == pytest.approx(25.0)


def test_universe_report_cli_format(session: Session) -> None:
    _seed_universe(session)
    report = get_universe_analytics_report(session, top_volumes_limit=2)
    text = universe_report.format_report(report, top_volumes=2, top_publishers=2)
    assert "P97 COMICVINE UNIVERSE ANALYTICS" in text
    assert "Huge" in text
    assert "Direct CV-Linked Existing Issues" in text
    assert "Coverage Percent" in text


def test_universe_analytics_empty_table(session: Session) -> None:
    report = get_universe_analytics_report(session)
    assert report.total_discovered_volumes == 0
    assert report.total_discoverable_issues == 0
    assert report.issues_not_yet_in_catalog == 0
    text = universe_report.format_report(report, top_volumes=5, top_publishers=5)
    assert "Total Discovered Volumes: 0" in text
