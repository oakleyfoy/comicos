"""P97 discovered-not-queued audit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue  # noqa: E402
from app.models.universe import UniverseVolume  # noqa: E402
from app.services.p97_core_publisher_mismatch_service import (  # noqa: E402
    STATUS_WRONG_PUBLISHER_MATCH,
    build_core_publisher_mismatch_report,
)
from app.services.p97_discovered_not_queued_service import (  # noqa: E402
    ACTION_ADD_TO_P97_QUEUE,
    build_discovered_not_queued_audit,
)
from app.services.p97_queue_priority_sanity_service import build_queue_priority_sanity_report  # noqa: E402
from app.services.p97_volume_issue_import_queue_service import STATUS_COMPLETE, STATUS_PENDING  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_tmnt_style_gap_identified(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=42285,
            name="Teenage Mutant Ninja Turtles",
            publisher="IDW Publishing",
            count_of_issues=150,
        )
    )
    session.add(
        UniverseVolume(
            comicvine_volume_id=42285,
            name="Teenage Mutant Ninja Turtles",
            publisher_id=1,
            normalized_name="teenage mutant ninja turtles",
        )
    )
    session.commit()
    rows = build_discovered_not_queued_audit(session)
    tmnt = [r for r in rows if r.comicvine_volume_id == 42285]
    assert len(tmnt) == 1
    assert tmnt[0].missing_issue_count == 150
    assert tmnt[0].p97_queue_status is None
    assert tmnt[0].recommended_action == ACTION_ADD_TO_P97_QUEUE
    assert tmnt[0].highlight_core


def test_complete_volume_with_active_queue_skipped(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=1, name="Done Book", publisher="Marvel", count_of_issues=0
        )
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=1,
            name="Done Book",
            publisher="Marvel",
            count_of_issues=5,
            existing_issue_count=5,
            missing_issue_count=0,
            coverage_percent=100.0,
            priority_score=1.0,
            launch_priority_tier="tier_3_other_us",
            status=STATUS_COMPLETE,
        )
    )
    session.commit()
    rows = build_discovered_not_queued_audit(session)
    assert not any(r.comicvine_volume_id == 1 for r in rows)


def test_pending_queue_with_missing_not_listed(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=2, name="Queued", publisher="Marvel", count_of_issues=20
        )
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=2,
            name="Queued",
            publisher="Marvel",
            count_of_issues=20,
            existing_issue_count=0,
            missing_issue_count=20,
            coverage_percent=0.0,
            priority_score=100.0,
            launch_priority_tier="tier_1_core",
            status=STATUS_PENDING,
        )
    )
    session.commit()
    rows = build_discovered_not_queued_audit(session)
    assert not any(r.comicvine_volume_id == 2 for r in rows)


def test_flash_publisher_mismatch_report(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=9001,
            name="Flash",
            publisher="ECC Ediciones",
            count_of_issues=100,
            start_year=2010,
        )
    )
    session.commit()
    rows = build_core_publisher_mismatch_report(session)
    flash_rows = [r for r in rows if r.core_title == "Flash"]
    assert flash_rows
    assert flash_rows[0].status == STATUS_WRONG_PUBLISHER_MATCH
    assert flash_rows[0].matched_publisher == "ECC Ediciones"


def test_priority_sanity_flags_tiny_high_priority(session: Session) -> None:
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=10,
            name="Rex Hart",
            publisher="Marvel",
            count_of_issues=3,
            existing_issue_count=0,
            missing_issue_count=3,
            coverage_percent=0.0,
            priority_score=900_000.0,
            launch_priority_tier="tier_3_other_us",
            status=STATUS_PENDING,
        )
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=11,
            name="Big Gap Run",
            publisher="Marvel",
            count_of_issues=200,
            existing_issue_count=0,
            missing_issue_count=200,
            coverage_percent=0.0,
            priority_score=50_000.0,
            launch_priority_tier="tier_3_other_us",
            status=STATUS_PENDING,
        )
    )
    session.commit()
    suspicious = build_queue_priority_sanity_report(session, top=10)
    names = {r.name for r in suspicious}
    assert "Rex Hart" in names
