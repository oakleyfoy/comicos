from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue  # noqa: E402
from app.services.p97_core_run_registry import (  # noqa: E402
    expected_publisher_for_report_label,
    pick_best_universe_match,
    publisher_matches_expected,
    volume_title_matches_report_label,
)
from app.services.p97_manual_volume_request_service import VolumeSearchCandidate  # noqa: E402
from app.services.p97_targeted_core_discovery import (  # noqa: E402
    apply_universe_discovery_candidate,
    build_core_discovery_status,
    missing_core_report_labels,
    search_core_run_candidates,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _universe(
    session: Session,
    *,
    volume_id: int,
    name: str,
    publisher: str | None,
    count_of_issues: int = 100,
    start_year: int | None = 1960,
) -> ComicVineVolumeUniverse:
    now = datetime.now(timezone.utc)
    row = ComicVineVolumeUniverse(
        volume_id=volume_id,
        name=name,
        publisher=publisher,
        start_year=start_year,
        count_of_issues=count_of_issues,
        first_discovered_at=now,
        last_discovered_at=now,
    )
    session.add(row)
    session.commit()
    return row


def test_publisher_matching_dc_marvel() -> None:
    assert publisher_matches_expected("DC Comics", "DC Comics")
    assert publisher_matches_expected("Marvel", "Marvel")
    assert not publisher_matches_expected("Williams Förlag AB", "DC Comics")


def test_flash_chooses_dc_over_foreign(session: Session) -> None:
    foreign = _universe(
        session,
        volume_id=1,
        name="Flash",
        publisher="Williams Förlag AB",
        count_of_issues=50,
        start_year=1990,
    )
    dc = _universe(
        session,
        volume_id=2,
        name="Flash",
        publisher="DC Comics",
        count_of_issues=800,
        start_year=1959,
    )
    best, pub_ok = pick_best_universe_match(
        [foreign, dc],
        "Flash",
        name_getter=lambda u: u.name,
        publisher_getter=lambda u: u.publisher,
        issue_count_getter=lambda u: u.count_of_issues,
        start_year_getter=lambda u: u.start_year,
    )
    assert best is not None
    assert int(best.volume_id) == int(dc.volume_id)
    assert pub_ok is True


def test_foreign_flash_rejected_when_only_foreign_present(session: Session) -> None:
    _universe(
        session,
        volume_id=3,
        name="Flash",
        publisher="Williams Förlag AB",
        count_of_issues=50,
    )
    rows, _ = build_core_discovery_status(session)
    flash = next(r for r in rows if r.report_label == "Flash")
    assert flash.discovered is True
    assert flash.publisher_match is False
    assert "Flash" in missing_core_report_labels(session)


def test_missing_uncanny_x_men_detection(session: Session) -> None:
    rows, summary = build_core_discovery_status(session)
    uncanny = next(r for r in rows if r.report_label == "Uncanny X-Men")
    assert uncanny.discovered is False
    assert "Uncanny X-Men" in missing_core_report_labels(session)
    assert summary.core_runs_missing >= 1


def test_discovery_report_after_marvel_uncanny_insert(session: Session) -> None:
    _universe(
        session,
        volume_id=100,
        name="Uncanny X-Men",
        publisher="Marvel",
        count_of_issues=544,
        start_year=1963,
    )
    rows, summary = build_core_discovery_status(session)
    uncanny = next(r for r in rows if r.report_label == "Uncanny X-Men")
    assert uncanny.discovered is True
    assert uncanny.publisher_match is True
    assert uncanny.issue_count == 544
    assert "Uncanny X-Men" not in missing_core_report_labels(session)
    assert summary.core_runs_discovered >= 1


def test_search_core_run_candidates_ranks_publisher(session: Session) -> None:
    client = MagicMock()
    client.fetch_volume_search_page.return_value = {
        "results": [
            {
                "id": "4050-1",
                "resource_type": "volume",
                "name": "Flash",
                "publisher": {"name": "Williams Förlag AB"},
                "count_of_issues": 12,
                "start_year": 1990,
            },
            {
                "id": "4050-2",
                "resource_type": "volume",
                "name": "Flash",
                "publisher": {"name": "DC Comics"},
                "count_of_issues": 900,
                "start_year": 1959,
            },
        ]
    }
    ranked = search_core_run_candidates(client, "Flash", search_limit=10)
    assert ranked
    assert ranked[0].volume_id == 2
    assert ranked[0].publisher_match is True


def test_apply_universe_inserts_row_without_queue(session: Session) -> None:
    client = MagicMock()
    client.fetch_volume_detail.return_value = {
        "results": {
            "id": "4050-200",
            "name": "Uncanny X-Men",
            "publisher": {"name": "Marvel"},
            "count_of_issues": 544,
            "start_year": 1963,
        }
    }
    action = apply_universe_discovery_candidate(session, client, volume_id=200)
    assert action == "inserted"
    row = session.exec(
        select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == 200)
    ).one()
    assert row.name == "Uncanny X-Men"
    assert row.publisher == "Marvel"
    queue_count = session.exec(select(P97VolumeIssueImportQueue)).all()
    assert queue_count == []


def test_volume_title_matches_report_label_asm_alias() -> None:
    assert volume_title_matches_report_label("The Amazing Spider-Man", "Amazing Spider-Man")
    assert expected_publisher_for_report_label("Amazing Spider-Man") == "Marvel"
