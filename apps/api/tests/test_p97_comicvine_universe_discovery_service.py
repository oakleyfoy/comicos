from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    UniverseDiscoveryProgress,
    discover_universe_batch,
    load_discovery_progress,
    parse_comicvine_datetime,
    save_discovery_progress,
    upsert_universe_volume,
    volume_row_from_api,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_parse_comicvine_datetime() -> None:
    assert parse_comicvine_datetime("2020-05-01 12:30:00") == datetime(
        2020, 5, 1, 12, 30, 0, tzinfo=timezone.utc
    )
    assert parse_comicvine_datetime(None) is None


def test_volume_row_from_api_parses_id_and_counts() -> None:
    parsed = volume_row_from_api(
        {
            "id": "4050-87154",
            "name": "Amazing Spider-Man",
            "start_year": 1963,
            "publisher": {"name": "Marvel"},
            "count_of_issues": 900,
            "date_added": "2010-01-01 00:00:00",
            "date_last_updated": "2024-01-01 00:00:00",
        }
    )
    assert parsed is not None
    assert parsed["volume_id"] == 87154
    assert parsed["publisher"] == "Marvel"
    assert parsed["count_of_issues"] == 900


def test_upsert_universe_volume_insert_then_update(session: Session) -> None:
    payload = {
        "volume_id": 100,
        "name": "Alpha",
        "publisher": "Marvel",
        "start_year": 2000,
        "count_of_issues": 12,
        "date_added": None,
        "date_last_updated": None,
    }
    assert upsert_universe_volume(session, payload) == "inserted"
    payload["count_of_issues"] = 15
    payload["name"] = "Alpha Updated"
    assert upsert_universe_volume(session, payload) == "updated"
    row = session.get(ComicVineVolumeUniverse, 1)
    assert row is not None
    assert row.count_of_issues == 15
    assert row.name == "Alpha Updated"


def test_discovery_progress_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    progress = UniverseDiscoveryProgress(offset=500, status="running", volumes_in_db=500)
    save_discovery_progress(path, progress)
    loaded = load_discovery_progress(path)
    assert loaded.offset == 500
    assert loaded.status == "running"
    assert loaded.volumes_in_db == 500
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["updated_at"]


def test_discover_universe_batch_upserts_and_advances_offset(session: Session) -> None:
    client = SimpleNamespace()

    def fake_fetch(*, offset: int, limit: int = 100):
        if offset == 0:
            return {
                "number_of_total_results": 150,
                "results": [
                    {"id": 1, "name": "A", "publisher": {"name": "Marvel"}, "count_of_issues": 10},
                    {"id": 2, "name": "B", "publisher": {"name": "DC"}, "count_of_issues": 20},
                ],
            }
        return {"results": []}

    client.fetch_volume_page = MagicMock(side_effect=fake_fetch)
    result = discover_universe_batch(session, client, offset=0, max_pages=2)
    assert result.pages_fetched == 1
    assert result.inserted == 2
    assert result.offset_after == 2
    assert result.number_of_total_results == 150
    assert result.complete is True
