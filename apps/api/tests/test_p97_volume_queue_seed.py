from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(API_ROOT), str(API_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.models  # noqa: F401,E402

from app.models.catalog_master import CatalogPublisher, CatalogSeries  # noqa: E402
from app.models.catalog_p97 import P97ComicVineVolumeQueue  # noqa: E402
from app.services.p97_volume_queue_service import (  # noqa: E402
    KNOWN_GOOD_MANUAL_SEEDS,
    SOURCE_MANUAL_SEED,
    get_queue_row,
    seed_known_good_manual,
    seed_known_good_volumes,
    upsert_queue_volume,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_known_good_manual_seeds_present() -> None:
    ids = {int(s["comicvine_volume_id"]) for s in KNOWN_GOOD_MANUAL_SEEDS}
    assert {87154, 56505, 152139} <= ids


def test_manual_seed_inserts_then_idempotent(session: Session) -> None:
    first = seed_known_good_manual(session)
    assert first.inserted == 3
    assert first.already_exists == 0
    row = get_queue_row(session, 87154)
    assert row is not None
    assert row.series_name == "Amazing Spider-Man"
    assert row.source_type == SOURCE_MANUAL_SEED
    assert row.status == "pending"

    # Second run must not duplicate rows.
    second = seed_known_good_manual(session)
    assert second.inserted == 0
    assert second.already_exists == 3
    total = len(session.exec(__import__("sqlmodel").select(P97ComicVineVolumeQueue)).all())
    assert total == 3


def test_seed_from_existing_catalog_picks_up_comicvine_volume_ids(session: Session) -> None:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        name="Venom",
        normalized_name="venom",
        publisher_id=publisher.id,
        external_source_ids={"COMICVINE": {"11068": True}},
    )
    session.add(series)
    session.commit()

    summary = seed_known_good_volumes(session)
    assert summary["inserted"] >= 4  # 3 manual + 1 from catalog
    row = get_queue_row(session, 11068)
    assert row is not None
    assert row.series_name == "Venom"
    assert summary["total_queue_pending"] >= 4
    assert summary["total_queue_imported"] == 0


def test_upsert_enriches_missing_metadata_only(session: Session) -> None:
    outcome, _ = upsert_queue_volume(session, comicvine_volume_id=999, series_name=None)
    assert outcome == "inserted"
    # Fill missing series_name -> updated.
    outcome, row = upsert_queue_volume(session, comicvine_volume_id=999, series_name="Spawn", publisher="Image")
    assert outcome == "updated"
    assert row is not None and row.series_name == "Spawn"
    # No new info -> already_exists, no overwrite of existing series_name.
    outcome, row = upsert_queue_volume(session, comicvine_volume_id=999, series_name="DifferentName")
    assert outcome == "already_exists"
    assert row.series_name == "Spawn"


def test_dry_run_does_not_write(session: Session) -> None:
    from sqlmodel import select

    summary = seed_known_good_volumes(session, dry_run=True)
    assert summary["dry_run"] is True
    assert summary["inserted"] == 3
    assert session.exec(select(P97ComicVineVolumeQueue)).all() == []
