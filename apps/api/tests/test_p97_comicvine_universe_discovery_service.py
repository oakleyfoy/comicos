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
    DISCOVERY_MODE_SEARCH,
    ComicVineEndpointForbiddenError,
    UniverseDiscoveryProgress,
    discover_universe_batch,
    filter_volume_search_rows,
    load_discovery_progress,
    parse_comicvine_datetime,
    save_discovery_progress,
    search_discovery_buckets,
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


def test_filter_volume_search_rows() -> None:
    rows = [
        {"id": "4050-1", "resource_type": "volume", "name": "A"},
        {"id": "4020-2", "resource_type": "issue", "name": "B"},
    ]
    assert len(filter_volume_search_rows(rows)) == 1


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
    progress = UniverseDiscoveryProgress(
        offset=500,
        status="running",
        volumes_in_db=500,
        discovery_mode=DISCOVERY_MODE_SEARCH,
        list_endpoint_forbidden=True,
        search_bucket_index=3,
    )
    save_discovery_progress(path, progress)
    loaded = load_discovery_progress(path)
    assert loaded.offset == 500
    assert loaded.discovery_mode == DISCOVERY_MODE_SEARCH
    assert loaded.list_endpoint_forbidden is True
    assert loaded.search_bucket_index == 3
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["updated_at"]


def test_discover_universe_batch_list_mode(session: Session) -> None:
    client = SimpleNamespace()
    progress = UniverseDiscoveryProgress()

    def fake_fetch(*, offset: int, limit: int = 100):
        if offset == 0:
            return {
                "number_of_total_results": 150,
                "results": [
                    {"id": "4050-1", "name": "A", "publisher": {"name": "Marvel"}, "count_of_issues": 10},
                    {"id": "4050-2", "name": "B", "publisher": {"name": "DC"}, "count_of_issues": 20},
                ],
            }
        return {"results": []}

    client.fetch_volume_list_page = MagicMock(side_effect=fake_fetch)
    result = discover_universe_batch(session, client, progress, max_pages=2)
    assert result.pages_fetched == 1
    assert result.inserted == 2
    assert progress.offset == 2
    assert result.complete is True


def test_list_403_switches_to_search(session: Session) -> None:
    client = SimpleNamespace()
    progress = UniverseDiscoveryProgress()

    def fake_list(*, offset: int, limit: int = 100):
        raise ComicVineEndpointForbiddenError("403 list")

    def fake_search(*, query: str, offset: int, limit: int = 10):
        assert query == search_discovery_buckets()[0]
        return {
            "results": [
                {
                    "id": "4050-9",
                    "name": "Nine",
                    "resource_type": "volume",
                    "publisher": {"name": "Marvel"},
                    "count_of_issues": 9,
                }
            ]
        }

    client.fetch_volume_list_page = MagicMock(side_effect=fake_list)
    client.fetch_volume_search_page = MagicMock(side_effect=fake_search)
    result = discover_universe_batch(session, client, progress, max_pages=1)
    assert progress.discovery_mode == DISCOVERY_MODE_SEARCH
    assert progress.list_endpoint_forbidden is True
    assert result.inserted == 1
    assert result.endpoint_forbidden is False


def test_search_403_sets_endpoint_forbidden(session: Session) -> None:
    client = SimpleNamespace()
    progress = UniverseDiscoveryProgress(discovery_mode=DISCOVERY_MODE_SEARCH)

    client.fetch_volume_search_page = MagicMock(
        side_effect=ComicVineEndpointForbiddenError("403 search")
    )
    result = discover_universe_batch(session, client, progress, max_pages=1)
    assert result.endpoint_forbidden is True
    assert progress.status == "endpoint_forbidden"
