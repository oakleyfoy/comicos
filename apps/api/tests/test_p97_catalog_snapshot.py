from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.p97_catalog_snapshot_service import export_catalog_snapshot, import_catalog_snapshot
from app.services.recognition.recognition_catalog_candidate_service import search_catalog_candidates


@pytest.fixture()
def session(tmp_path: Path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s, tmp_path


def _seed_absolute_batman(session: Session) -> None:
    publisher = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        name="Absolute Batman",
        normalized_name=normalize_series_name("Absolute Batman"),
        publisher_id=publisher.id,
        start_year=2024,
        external_source_ids={"COMICVINE": {"160294": True}},
    )
    session.add(series)
    session.flush()
    for number in range(1, 4):
        issue = CatalogIssue(
            series_id=int(series.id or 0),
            publisher_id=publisher.id,
            issue_number=str(number),
            normalized_issue_number=normalize_issue_number(str(number)),
            cover_date=date(2024, 12, 1),
            release_date=date(2024, 10, 7),
            external_source_ids={"COMICVINE": {str(1_000_000 + number): True}, "_primary_source": "COMICVINE"},
        )
        session.add(issue)
        session.flush()
        session.add(
            CatalogImage(
                issue_id=issue.id,
                image_type="cover",
                source_url=f"https://example.com/abs-batman-{number}.jpg",
                source="comicvine",
            )
        )
    session.commit()


def test_import_logs_index_phases(session) -> None:
    db_session, tmp_path = session
    _seed_absolute_batman(db_session)
    snapshot_path = tmp_path / "snapshot.jsonl"
    export_catalog_snapshot(db_session, snapshot_path, volume_ids=[160294])

    import_stats = import_catalog_snapshot(db_session, snapshot_path, dry_run=True, verbose=True)
    phase_names = [p.phase for p in import_stats.index_phases]
    assert "_build_publisher_index" in phase_names
    assert "_build_series_index" in phase_names
    assert "_build_issue_index" in phase_names
    assert "_build_image_index" in phase_names


def test_export_import_volume_snapshot_is_idempotent(session) -> None:
    db_session, tmp_path = session
    _seed_absolute_batman(db_session)
    snapshot_path = tmp_path / "snapshot.jsonl"

    export_stats = export_catalog_snapshot(
        db_session,
        snapshot_path,
        volume_ids=[160294],
    )
    assert export_stats.publishers == 1
    assert export_stats.series == 1
    assert export_stats.issues == 3
    assert export_stats.images == 3

    import_stats = import_catalog_snapshot(db_session, snapshot_path, dry_run=True)
    assert import_stats.series_updated == 1
    assert import_stats.issues_updated == 3
    assert import_stats.images_updated == 3

    import_stats = import_catalog_snapshot(db_session, snapshot_path, dry_run=False)
    assert import_stats.series_updated == 1
    assert import_stats.issues_updated == 3

    second = import_catalog_snapshot(db_session, snapshot_path, dry_run=False)
    assert second.series_created == 0
    assert second.issues_created == 0
    assert second.images_created == 0


def test_imported_snapshot_is_searchable(session) -> None:
    db_session, tmp_path = session
    _seed_absolute_batman(db_session)
    snapshot_path = tmp_path / "snapshot.jsonl"
    export_catalog_snapshot(db_session, snapshot_path, volume_ids=[160294])

    # Target DB starts empty except what we re-import
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as target:
        import_catalog_snapshot(target, snapshot_path, dry_run=False)
        cards = search_catalog_candidates(target, q="absolute batman", limit=24)
        assert len(cards) == 3
        assert cards[0].series == "Absolute Batman"
