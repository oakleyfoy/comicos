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
from app.services.p97_comicvine_universe_analytics_service import get_universe_analytics_report  # noqa: E402
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


def _seed_catalog(session: Session, count: int) -> None:
    pub = CatalogPublisher(name="Pub", normalized_name="pub")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    series = CatalogSeries(name="Series", normalized_name="series", publisher_id=pub.id)
    session.add(series)
    session.commit()
    session.refresh(series)
    for i in range(count):
        num = str(i + 1)
        session.add(
            CatalogIssue(series_id=series.id, issue_number=num, normalized_issue_number=num)
        )
    session.commit()


def test_universe_analytics_totals_and_sorting(session: Session) -> None:
    _seed_universe(session)
    _seed_catalog(session, 50)
    report = get_universe_analytics_report(session, top_volumes_limit=10, top_publishers_limit=5)
    assert report.total_discovered_volumes == 3
    assert report.total_discoverable_issues == 1105
    assert report.current_catalog_issues == 50
    assert report.projected_comicos_catalog_ceiling == 1105
    assert report.issues_not_yet_in_catalog == 1055
    assert [row.volume_id for row in report.largest_volumes] == [1, 3, 2]
    assert report.top_publishers[0].publisher == "Marvel"
    assert report.top_publishers[0].total_issues == 1100


def test_universe_report_cli_format(session: Session) -> None:
    _seed_universe(session)
    report = get_universe_analytics_report(session, top_volumes_limit=2)
    text = universe_report.format_report(report, top_volumes=2, top_publishers=2)
    assert "P97 COMICVINE UNIVERSE ANALYTICS" in text
    assert "Huge" in text
    assert "Projected Catalog Ceiling" in text
