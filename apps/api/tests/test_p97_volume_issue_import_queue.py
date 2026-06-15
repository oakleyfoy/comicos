from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries  # noqa: E402
from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue  # noqa: E402
from app.services.catalog_ingestion_service import normalize_series_name  # noqa: E402
from app.services.p97_volume_issue_queue_priority import (  # noqa: E402
    TIER_0_MANUAL,
    TIER_1_CORE,
    TIER_4_DEPRIORITIZED,
    MANUAL_REQUEST_PRIORITY_SCORE,
    compute_volume_import_priority,
)
from app.services.p97_volume_issue_import_queue_service import (  # noqa: E402
    STATUS_COMPLETE,
    STATUS_PENDING,
    STATUS_RUNNING,
    build_volume_issue_import_queue,
    get_top_queued_volumes,
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
    volume_id: int,
    *,
    name: str,
    publisher: str,
    count: int,
) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=volume_id,
            name=name,
            publisher=publisher,
            count_of_issues=count,
        )
    )
    session.commit()


def _catalog_series_with_issues(
    session: Session,
    *,
    name: str,
    publisher: str,
    issue_count: int,
    comicvine_volume_id: int | None = None,
) -> None:
    pub = CatalogPublisher(name=publisher, normalized_name=normalize_series_name(publisher))
    session.add(pub)
    session.commit()
    session.refresh(pub)
    ext = {"COMICVINE": {str(comicvine_volume_id): "volume"}} if comicvine_volume_id else None
    series = CatalogSeries(
        name=name,
        normalized_name=normalize_series_name(name),
        publisher_id=pub.id,
        external_source_ids=ext,
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    for i in range(issue_count):
        num = str(i + 1)
        session.add(
            CatalogIssue(series_id=series.id, issue_number=num, normalized_issue_number=num)
        )
    session.commit()


def test_queue_inserts_missing_volume(session: Session) -> None:
    _universe(session, 100, name="X-Men", publisher="Marvel", count=50)
    result = build_volume_issue_import_queue(session)
    assert result.queue_rows_inserted == 1
    row = session.exec(select(P97VolumeIssueImportQueue)).one()
    assert row.comicvine_volume_id == 100
    assert row.missing_issue_count == 50
    assert row.status == STATUS_PENDING
    assert row.launch_priority_tier == TIER_1_CORE


def test_skips_fully_covered_volume(session: Session) -> None:
    _universe(session, 87154, name="Amazing Spider-Man", publisher="Marvel", count=10)
    _catalog_series_with_issues(
        session,
        name="Amazing Spider-Man",
        publisher="Marvel",
        issue_count=10,
        comicvine_volume_id=87154,
    )
    result = build_volume_issue_import_queue(session)
    assert result.queue_rows_inserted == 0
    assert result.skipped_complete == 1
    assert session.exec(select(P97VolumeIssueImportQueue)).first() is None


def test_preserves_complete_row(session: Session) -> None:
    _universe(session, 200, name="Batman", publisher="DC Comics", count=100)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=200,
            name="Batman",
            publisher="DC Comics",
            count_of_issues=80,
            existing_issue_count=0,
            missing_issue_count=80,
            coverage_percent=0.0,
            priority_score=1000.0,
            launch_priority_tier=TIER_1_CORE,
            status=STATUS_COMPLETE,
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    result = build_volume_issue_import_queue(session)
    assert result.skipped_protected == 1
    row = session.exec(select(P97VolumeIssueImportQueue)).one()
    assert row.status == STATUS_COMPLETE
    assert row.missing_issue_count == 80


def test_refresh_complete_updates_complete_row(session: Session) -> None:
    _universe(session, 200, name="Batman", publisher="DC Comics", count=100)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=200,
            name="Batman",
            publisher="DC Comics",
            count_of_issues=80,
            existing_issue_count=0,
            missing_issue_count=80,
            coverage_percent=0.0,
            priority_score=1000.0,
            launch_priority_tier=TIER_1_CORE,
            status=STATUS_COMPLETE,
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    result = build_volume_issue_import_queue(session, refresh_complete=True)
    assert result.queue_rows_updated == 1
    row = session.exec(select(P97VolumeIssueImportQueue)).one()
    assert row.status == STATUS_PENDING
    assert row.missing_issue_count == 100
    assert row.completed_at is None


def test_marvel_core_beats_huge_foreign_missing(session: Session) -> None:
    marvel = compute_volume_import_priority(
        missing_issue_count=40,
        count_of_issues=800,
        coverage_percent=95.0,
        publisher="Marvel",
        name="The Avengers",
    )
    foreign = compute_volume_import_priority(
        missing_issue_count=2000,
        count_of_issues=2000,
        coverage_percent=0.0,
        publisher="Panini Comics",
        name="Topolino",
    )
    assert marvel.priority_score > foreign.priority_score


def test_queue_ranking_prefers_us_core(session: Session) -> None:
    _universe(session, 1, name="Topolino", publisher="Panini Comics", count=1500)
    _universe(session, 2, name="Detective Comics", publisher="DC Comics", count=900)
    _universe(session, 3, name="The Amazing Spider-Man", publisher="Marvel", count=900)
    build_volume_issue_import_queue(session)
    top = get_top_queued_volumes(session, limit=3)
    names = [row.name for row in top]
    assert names[0] in {"Detective Comics", "The Amazing Spider-Man"}
    assert "Topolino" not in names[0]


def test_rebuild_fixes_pending_wrong_tier_for_topolino(session: Session) -> None:
    _universe(session, 9001, name="Topolino", publisher="Panini Comics", count=120)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=9001,
            name="Topolino",
            publisher="Panini Comics",
            count_of_issues=120,
            existing_issue_count=0,
            missing_issue_count=120,
            coverage_percent=0.0,
            priority_score=50_000.0,
            launch_priority_tier="tier_3_other_us",
            status=STATUS_PENDING,
        )
    )
    session.commit()
    build_volume_issue_import_queue(session)
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 9001
        )
    ).one()
    assert row.launch_priority_tier == TIER_4_DEPRIORITIZED


def test_complete_manual_tier_0_unchanged_after_rebuild(session: Session) -> None:
    _universe(session, 160294, name="Absolute Batman", publisher="DC Comics", count=12)
    completed_at = datetime.now(timezone.utc)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=160294,
            name="Absolute Batman",
            publisher="DC Comics",
            count_of_issues=12,
            existing_issue_count=12,
            missing_issue_count=0,
            coverage_percent=100.0,
            priority_score=MANUAL_REQUEST_PRIORITY_SCORE,
            launch_priority_tier=TIER_0_MANUAL,
            request_notes="scanner testing",
            status=STATUS_COMPLETE,
            completed_at=completed_at,
        )
    )
    session.commit()
    build_volume_issue_import_queue(session)
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 160294
        )
    ).one()
    assert row.launch_priority_tier == TIER_0_MANUAL
    assert row.priority_score == MANUAL_REQUEST_PRIORITY_SCORE
    assert row.status == STATUS_COMPLETE
    assert row.request_notes == "scanner testing"
    assert row.missing_issue_count == 0
    assert row.completed_at is not None


def test_running_row_not_updated(session: Session) -> None:
    _universe(session, 300, name="Saga", publisher="Image", count=60)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=300,
            name="Old",
            publisher="Image",
            count_of_issues=10,
            existing_issue_count=0,
            missing_issue_count=10,
            coverage_percent=0.0,
            priority_score=1.0,
            launch_priority_tier=TIER_1_CORE,
            status=STATUS_RUNNING,
            started_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    result = build_volume_issue_import_queue(session)
    assert result.skipped_protected == 1
    row = session.exec(select(P97VolumeIssueImportQueue)).one()
    assert row.name == "Old"
    assert row.status == STATUS_RUNNING
