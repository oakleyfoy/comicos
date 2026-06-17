"""P98 discovery integrity — probe and dual-table membership."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.models.universe import UniverseVolume  # noqa: E402
from app.services.p98_discovery_integrity_service import (  # noqa: E402
    membership_for,
    probe_publisher_volumes,
)
from app.services.p98_missing_volume_discovery_service import (  # noqa: E402
    discover_missing_volumes_for_publisher,
)
from app.services.p98_major_publisher_registry import resolve_major_publisher  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _marvel_payload() -> dict:
    return {
        "results": [
            {
                "id": "4050-100",
                "name": "Existing In Both",
                "publisher": {"name": "Marvel"},
                "count_of_issues": 10,
                "start_year": 2020,
            },
            {
                "id": "4050-200",
                "name": "CV Only",
                "publisher": {"name": "Marvel"},
                "count_of_issues": 12,
                "start_year": 2021,
            },
            {
                "id": "4050-300",
                "name": "Missing Both",
                "publisher": {"name": "Marvel"},
                "count_of_issues": 5,
                "start_year": 2022,
            },
        ]
    }


def test_probe_formats_rows_with_dual_membership(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=100, name="Existing In Both", publisher="Marvel", count_of_issues=10
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=200, name="CV Only", publisher="Marvel", count_of_issues=12
        )
    )
    session.add(
        UniverseVolume(
            comicvine_volume_id=100,
            name="Existing In Both",
            publisher_id=1,
            normalized_name="existing in both",
        )
    )
    session.commit()

    client = MagicMock()
    client.fetch_publisher_volumes_page.return_value = _marvel_payload()
    report = probe_publisher_volumes(
        session, client, publisher="Marvel", limit_pages=1, max_display_rows=25
    )
    assert report.total_scanned == 3
    assert report.in_cv_universe == 2
    assert report.in_p98_universe == 1
    assert report.missing_from_both == 1
    assert report.missing_from_p98_only == 1
    assert len(report.rows) == 3
    by_id = {r.comicvine_volume_id: r for r in report.rows}
    assert by_id[100].in_comicvine_volume_universe and by_id[100].in_universe_volume
    assert by_id[200].in_comicvine_volume_universe and not by_id[200].in_universe_volume
    assert not by_id[300].in_comicvine_volume_universe and not by_id[300].in_universe_volume


def test_membership_for(session: Session) -> None:
    session.add(ComicVineVolumeUniverse(volume_id=42, name="X", publisher="Marvel", count_of_issues=1))
    session.commit()
    m = membership_for(session, 42)
    assert m.in_comicvine_volume_universe
    assert not m.in_universe_volume
    assert m.missing_from_p98_only


def test_discovery_report_dual_table_counts(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(volume_id=100, name="In Both", publisher="Marvel", count_of_issues=10)
    )
    session.add(
        ComicVineVolumeUniverse(volume_id=200, name="CV Only", publisher="Marvel", count_of_issues=12)
    )
    session.add(
        UniverseVolume(
            comicvine_volume_id=100,
            name="In Both",
            publisher_id=1,
            normalized_name="in both",
        )
    )
    session.commit()
    config = resolve_major_publisher("Marvel")
    assert config is not None
    client = MagicMock()
    client.fetch_publisher_volumes_page.return_value = _marvel_payload()
    report = discover_missing_volumes_for_publisher(
        session, client, config, limit_pages=1, limit_volumes=50, apply=False
    )
    assert report.comicvine_volumes_scanned == 3
    assert report.already_in_comicvine_universe == 2
    assert report.already_in_universe == 1
    assert report.missing_from_p98_only == 1
    assert report.missing_from_both == 1
    assert report.missing_from_universe == 2
