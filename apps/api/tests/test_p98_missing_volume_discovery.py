"""P98 — missing major-publisher volume discovery tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniverseVariant, UniverseVolume
from app.services.p98_major_publisher_registry import resolve_major_publisher
from app.services.p98_missing_volume_discovery_service import (
    ACTION_INSERT_VOLUME_ONLY,
    MissingVolumeCandidate,
    PublisherDiscoveryProgress,
    apply_missing_volume,
    build_missing_volume_action_queue,
    discover_missing_volumes_for_publisher,
    get_volume_expansion_candidates_from_local_db,
    load_discovery_progress,
    save_discovery_progress,
    universe_comicvine_volume_ids,
)
from app.services.universe.universe_issue_service import VOLUME_STATUS_VOLUME_ONLY
from app.services.universe.universe_publisher_service import build_publishers_from_discovered_volumes
from app.services.universe.universe_volume_service import build_volumes_from_discovered_universe
from test_p98_skeleton_gap_service import seed_gap


def test_publisher_alias_mapping() -> None:
    assert resolve_major_publisher("Marvel") is not None
    assert resolve_major_publisher("marvel comics") is not None
    assert resolve_major_publisher("DC") is not None
    assert resolve_major_publisher("BOOM! Studios") is not None
    assert resolve_major_publisher("Random House") is None


def test_existing_volume_detection(client: TestClient, session: Session) -> None:
    seed_gap(session)
    ids = universe_comicvine_volume_ids(session)
    assert 88001 in ids
    assert 99999 not in ids


def test_local_missing_detection(client: TestClient, session: Session) -> None:
    seed_gap(session)
    session.add(
        ComicVineVolumeUniverse(
            volume_id=99001,
            name="New Marvel Series",
            publisher="Marvel",
            start_year=2020,
            count_of_issues=12,
        )
    )
    session.commit()
    missing = get_volume_expansion_candidates_from_local_db(session)
    assert any(c.comicvine_volume_id == 99001 for c in missing)


def _marvel_page(*, offset: int, include_missing: bool = True) -> dict:
    rows = [
        {
            "id": "4050-88001",
            "name": "Amazing Spider-Man",
            "start_year": 1963,
            "publisher": {"name": "Marvel"},
            "count_of_issues": 900,
        }
    ]
    if include_missing:
        rows.append(
            {
                "id": "4050-99002",
                "name": "Brand New Marvel Vol",
                "start_year": 2024,
                "publisher": {"name": "Marvel"},
                "count_of_issues": 6,
            }
        )
    return {"results": rows, "number_of_total_results": len(rows)}


def test_missing_volume_detection_mock_api(client: TestClient, session: Session) -> None:
    seed_gap(session)
    config = resolve_major_publisher("Marvel")
    assert config is not None
    client_mock = MagicMock()
    client_mock.fetch_publisher_volumes_page.return_value = _marvel_page(offset=0)
    report = discover_missing_volumes_for_publisher(
        session,
        client_mock,
        config,
        limit_pages=1,
        apply=False,
        resume=False,
    )
    assert report.comicvine_volumes_scanned == 2
    assert report.already_in_universe >= 1
    assert report.missing_from_universe == 1
    assert report.missing_candidates[0].comicvine_volume_id == 99002
    client_mock.fetch_publisher_volumes_page.assert_called_once()


def test_dry_run_does_not_insert(client: TestClient, session: Session) -> None:
    seed_gap(session)
    before = len(session.exec(select(UniverseVolume)).all())
    config = resolve_major_publisher("Marvel")
    client_mock = MagicMock()
    client_mock.fetch_publisher_volumes_page.return_value = _marvel_page(offset=0)
    discover_missing_volumes_for_publisher(
        session,
        client_mock,
        config,
        limit_pages=1,
        apply=False,
        resume=False,
    )
    assert len(session.exec(select(UniverseVolume)).all()) == before


def test_apply_inserts_universe_volume(client: TestClient, session: Session) -> None:
    seed_gap(session)
    issues_before = len(session.exec(select(UniverseIssue)).all())
    variants_before = len(session.exec(select(UniverseVariant)).all())
    config = resolve_major_publisher("Marvel")
    client_mock = MagicMock()
    client_mock.fetch_publisher_volumes_page.return_value = {
        "results": [
            {
                "id": "4050-99003",
                "name": "Inserted Vol",
                "start_year": 2019,
                "publisher": {"name": "Marvel"},
                "count_of_issues": 5,
            }
        ]
    }
    report = discover_missing_volumes_for_publisher(
        session,
        client_mock,
        config,
        limit_pages=1,
        apply=True,
        resume=False,
    )
    assert report.inserted == 1
    vol = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 99003)).first()
    assert vol is not None
    assert vol.volume_status == VOLUME_STATUS_VOLUME_ONLY
    cv = session.exec(
        select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == 99003)
    ).first()
    assert cv is not None
    assert len(session.exec(select(UniverseIssue)).all()) == issues_before
    assert len(session.exec(select(UniverseVariant)).all()) == variants_before


def test_throttle_stops_when_configured(client: TestClient, session: Session) -> None:
    from app.services.comicvine_catalog_importer import ComicVineThrottleError

    seed_gap(session)
    config = resolve_major_publisher("Marvel")
    client_mock = MagicMock()
    client_mock.fetch_publisher_volumes_page.side_effect = ComicVineThrottleError("420")
    report = discover_missing_volumes_for_publisher(
        session,
        client_mock,
        config,
        limit_pages=5,
        apply=False,
        stop_on_throttle=True,
        resume=False,
    )
    assert report.throttled is True
    assert report.stopped is True


def test_progress_file_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    progress = {"publishers": {"Marvel": PublisherDiscoveryProgress(publisher="Marvel", offset=200).to_dict()}}
    save_discovery_progress(progress, path)
    loaded = load_discovery_progress(path)
    assert loaded["publishers"]["Marvel"]["offset"] == 200


def test_action_queue_json(client: TestClient, session: Session, tmp_path: Path) -> None:
    seed_gap(session)
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps(
            {
                "all_missing": [
                    MissingVolumeCandidate(
                        publisher="Marvel",
                        volume="X",
                        comicvine_volume_id=99004,
                        start_year=2020,
                        issue_count=3,
                        priority_score=100,
                        reason="test",
                        recommended_action=ACTION_INSERT_VOLUME_ONLY,
                    ).as_dict()
                ]
            }
        ),
        encoding="utf-8",
    )
    rows = build_missing_volume_action_queue(session, results_path=results, include_local_db=False)
    assert len(rows) == 1
    assert rows[0]["recommended_action"] == ACTION_INSERT_VOLUME_ONLY
