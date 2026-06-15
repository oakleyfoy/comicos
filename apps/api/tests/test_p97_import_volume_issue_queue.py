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

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries  # noqa: E402
from app.models.catalog_p97 import P97VolumeIssueImportQueue  # noqa: E402
from app.services.catalog_ingestion_service import normalize_series_name  # noqa: E402
from app.services.comicvine_catalog_importer import ComicVineImportStats  # noqa: E402
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget  # noqa: E402
from app.services.p97_volume_issue_import_queue_service import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_PENDING,
)
from app.services.p97_volume_issue_queue_import_service import (
    run_volume_issue_queue_import,
    select_pending_volume_issue_imports,
)
from app.services.p97_volume_issue_queue_priority import (  # noqa: E402
    TIER_1_CORE,
    TIER_4_DEPRIORITIZED,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _catalog_series_with_issues(
    session: Session,
    *,
    name: str,
    publisher: str,
    issue_count: int,
    comicvine_volume_id: int,
) -> None:
    pub = CatalogPublisher(name=publisher, normalized_name=normalize_series_name(publisher))
    session.add(pub)
    session.commit()
    session.refresh(pub)
    series = CatalogSeries(
        name=name,
        normalized_name=normalize_series_name(name),
        publisher_id=pub.id,
        external_source_ids={"COMICVINE": {str(comicvine_volume_id): "volume"}},
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


def _queue_row(
    session: Session,
    *,
    volume_id: int,
    name: str,
    tier: str,
    score: float,
    status: str = STATUS_PENDING,
) -> None:
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=volume_id,
            name=name,
            publisher="Marvel" if tier == TIER_1_CORE else "Panini Comics",
            count_of_issues=10,
            existing_issue_count=0,
            missing_issue_count=10,
            coverage_percent=0.0,
            priority_score=score,
            launch_priority_tier=tier,
            status=status,
        )
    )
    session.commit()


class FakeImporter:
    def __init__(self, *, dry_run: bool = False, behavior: str = "success") -> None:
        self.dry_run = dry_run
        self.behavior = behavior
        self.calls: list[int] = []

    def import_single_volume(self, session, *, comicvine_volume_id, import_issues, issues_per_volume_limit):
        del session, import_issues, issues_per_volume_limit
        self.calls.append(int(comicvine_volume_id))
        stats = ComicVineImportStats(volume_id=int(comicvine_volume_id))
        stats.api_requests_used = 2
        if self.dry_run:
            return stats
        if self.behavior == "fail":
            stats.failures.append("volume_lookup:404")
            return stats
        if self.behavior == "throttle":
            stats.throttled = True
            stats.failures.append("ComicVine HTTP 420")
            return stats
        if self.behavior == "connection_reset":
            stats.failures.append("connection reset by peer")
            return stats
        if self.behavior == "idempotent":
            if len(self.calls) == 1:
                stats.created_issues = 5
            else:
                stats.updated_issues = 5
            return stats
        stats.created_issues = 10
        stats.updated_issues = 0
        return stats


def test_dry_run_changes_no_rows(session: Session) -> None:
    _queue_row(session, volume_id=1, name="A", tier=TIER_1_CORE, score=200_000)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter(dry_run=True)
    result = run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=5,
        dry_run=True,
    )
    assert result.volumes_processed == 1
    row = session.exec(select(P97VolumeIssueImportQueue)).one()
    assert row.status == STATUS_PENDING
    assert row.attempts == 0


def test_imports_highest_priority_tier_1_first(session: Session) -> None:
    _queue_row(session, volume_id=1, name="Low", tier=TIER_1_CORE, score=100_010)
    _queue_row(session, volume_id=2, name="High", tier=TIER_1_CORE, score=100_500)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter()
    run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=1,
    )
    assert importer.calls == [2]


def test_skips_tier_4_by_default(session: Session) -> None:
    _queue_row(session, volume_id=9, name="Topolino", tier=TIER_4_DEPRIORITIZED, score=999_999)
    _queue_row(session, volume_id=2, name="Spider", tier=TIER_1_CORE, score=100_000)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter()
    selected = select_pending_volume_issue_imports(session, limit=10)
    assert len(selected) == 1
    assert selected[0].comicvine_volume_id == 2
    run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        limit_volumes=5,
    )
    assert importer.calls == [2]


def test_marks_complete_on_success(session: Session) -> None:
    _queue_row(session, volume_id=42, name="Detective", tier=TIER_1_CORE, score=100_000)
    _catalog_series_with_issues(
        session,
        name="Detective",
        publisher="Marvel",
        issue_count=10,
        comicvine_volume_id=42,
    )
    budget = ComicVineRateBudget(session)
    importer = FakeImporter()
    result = run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=1,
    )
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 42
        )
    ).one()
    assert result.volumes_complete == 1
    assert row.status == STATUS_COMPLETE
    assert row.attempts == 1


def test_marks_failed_on_importer_exception_result(session: Session) -> None:
    _queue_row(session, volume_id=55, name="Missing", tier=TIER_1_CORE, score=100_000)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter(behavior="fail")
    run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=1,
    )
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 55
        )
    ).one()
    assert row.status == STATUS_FAILED
    assert row.last_error
    assert row.attempts == 1


def test_stops_cleanly_on_throttle(session: Session) -> None:
    _queue_row(session, volume_id=1, name="One", tier=TIER_1_CORE, score=100_500)
    _queue_row(session, volume_id=2, name="Two", tier=TIER_1_CORE, score=100_400)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter(behavior="throttle")
    result = run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=5,
        stop_on_throttle=True,
    )
    assert result.stopped_reason == "throttle"
    assert len(importer.calls) == 1
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 1
        )
    ).one()
    assert row.status == STATUS_PENDING
    pending_second = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 2
        )
    ).one()
    assert pending_second.status == STATUS_PENDING


def test_stops_cleanly_on_connection_reset(session: Session) -> None:
    _queue_row(session, volume_id=3, name="Three", tier=TIER_1_CORE, score=100_300)
    _queue_row(session, volume_id=4, name="Four", tier=TIER_1_CORE, score=100_200)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter(behavior="connection_reset")
    result = run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=5,
        stop_on_throttle=True,
    )
    assert result.stopped_reason == "connection_reset"
    assert len(importer.calls) == 1


def test_idempotent_rerun_updates_not_duplicate(session: Session) -> None:
    _queue_row(session, volume_id=77, name="Repeat", tier=TIER_1_CORE, score=100_000)
    budget = ComicVineRateBudget(session)
    importer = FakeImporter(behavior="idempotent")
    first = run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=1,
    )
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 77
        )
    ).one()
    row.status = STATUS_PENDING
    row.missing_issue_count = 5
    session.add(row)
    session.commit()
    second = run_volume_issue_queue_import(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        tier=TIER_1_CORE,
        limit_volumes=1,
    )
    assert first.items[0].created_issues == 5
    assert second.items[0].created_issues == 0
    assert second.items[0].updated_issues == 5
    assert len(importer.calls) == 2
