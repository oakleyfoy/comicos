from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries  # noqa: E402
from app.services.catalog_ingestion_service import normalize_series_name, upsert_issue  # noqa: E402
from app.services.comicvine_api_response import (  # noqa: E402
    comicvine_issue_dates_from_row,
    parse_comicvine_date,
)
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter  # noqa: E402


def test_parse_comicvine_date() -> None:
    assert parse_comicvine_date("2024-10-01 00:00:00") == date(2024, 10, 1)
    assert parse_comicvine_date("2024-10-01") == date(2024, 10, 1)
    assert parse_comicvine_date(None) is None
    assert parse_comicvine_date("") is None


def test_comicvine_issue_dates_from_row_prefers_release_then_date_added() -> None:
    cover, store, release = comicvine_issue_dates_from_row(
        {
            "cover_date": "2024-10-01 00:00:00",
            "store_date": "2024-10-08 00:00:00",
            "date_added": "2024-09-15 12:00:00",
        }
    )
    assert cover == date(2024, 10, 1)
    assert store == date(2024, 10, 8)
    assert release == date(2024, 9, 15)

    _, _, release_explicit = comicvine_issue_dates_from_row(
        {
            "release_date": "2024-11-01 00:00:00",
            "date_added": "2024-09-15 12:00:00",
        }
    )
    assert release_explicit == date(2024, 11, 1)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _series(session: Session, *, volume_id: str = "160294") -> CatalogSeries:
    pub = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    series = CatalogSeries(
        name="Absolute Batman",
        normalized_name=normalize_series_name("Absolute Batman"),
        publisher_id=pub.id,
        external_source_ids={"COMICVINE": {volume_id: "volume"}},
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    return series


def test_import_issues_for_volume_persists_dates(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    series = _series(session)
    payload = {
        "results": [
            {
                "id": 1073108,
                "issue_number": "1",
                "name": "Chapter One",
                "cover_date": "2024-10-01 00:00:00",
                "store_date": "2024-10-08 00:00:00",
                "date_added": "2024-09-20 00:00:00",
                "image": {"super_url": "https://example.com/cover.jpg"},
            }
        ]
    }

    def fake_get(self, path, params=None):  # noqa: ANN001
        del self, path, params
        return payload

    monkeypatch.setattr(ComicVineCatalogImporter, "_get", fake_get)
    importer = ComicVineCatalogImporter(api_key="x" * 20, dry_run=False)
    stats = importer.import_issues_for_volume(
        session,
        volume_id="160294",
        catalog_series_id=int(series.id or 0),
    )
    assert stats.created_issues == 1
    issue = session.exec(select(CatalogIssue)).one()
    assert issue.cover_date == date(2024, 10, 1)
    assert issue.store_date == date(2024, 10, 8)
    assert issue.release_date == date(2024, 9, 20)


def test_reimport_updates_dates_without_duplicates(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    series = _series(session)
    upsert_issue(
        session,
        series_id=int(series.id or 0),
        publisher_id=series.publisher_id,
        issue_number="1",
        source="COMICVINE",
        external_id=1073108,
        cover_date=None,
        store_date=None,
        release_date=None,
    )
    session.commit()

    payload = {
        "results": [
            {
                "id": 1073108,
                "issue_number": "1",
                "name": "Chapter One",
                "cover_date": "2024-10-01 00:00:00",
                "store_date": "2024-10-08 00:00:00",
                "date_added": "2024-09-20 00:00:00",
                "image": {},
            }
        ]
    }

    def fake_get(self, path, params=None):  # noqa: ANN001
        del self, path, params
        return payload

    monkeypatch.setattr(ComicVineCatalogImporter, "_get", fake_get)
    importer = ComicVineCatalogImporter(api_key="x" * 20, dry_run=False)
    stats = importer.import_issues_for_volume(
        session,
        volume_id="160294",
        catalog_series_id=int(series.id or 0),
    )
    assert stats.updated_issues == 1
    assert stats.created_issues == 0
    count = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())
    assert count == 1
    issue = session.exec(select(CatalogIssue)).one()
    assert issue.cover_date == date(2024, 10, 1)
    assert issue.store_date == date(2024, 10, 8)
    assert issue.release_date == date(2024, 9, 20)


def test_upsert_preserves_existing_date_from_higher_priority_source(session: Session) -> None:
    series = _series(session)
    existing = upsert_issue(
        session,
        series_id=int(series.id or 0),
        publisher_id=series.publisher_id,
        issue_number="1",
        source="MANUAL",
        cover_date=date(2020, 1, 1),
    )
    session.commit()
    updated = upsert_issue(
        session,
        series_id=int(series.id or 0),
        publisher_id=series.publisher_id,
        issue_number="1",
        source="COMICVINE",
        external_id=1,
        cover_date=date(2024, 10, 1),
    )
    session.commit()
    assert int(updated.id or 0) == int(existing.id or 0)
    assert updated.cover_date == date(2020, 1, 1)
