from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_master import CatalogIssue  # noqa: E402
from app.models.catalog_p97 import P97VolumeIssueImportQueue  # noqa: E402
from app.services.comicvine_catalog_importer import ComicVineImportStats  # noqa: E402
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget  # noqa: E402
from app.services.p97_requested_volume_import_service import import_requested_volume_issues  # noqa: E402
from app.services.p97_volume_issue_import_queue_service import STATUS_PENDING  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class FakeImporter:
    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.calls = 0

    def import_single_volume(self, session, *, comicvine_volume_id, import_issues, issues_per_volume_limit):
        del session, import_issues, issues_per_volume_limit
        self.calls += 1
        stats = ComicVineImportStats(volume_id=int(comicvine_volume_id))
        if self.dry_run:
            stats.issue_import_ran = True
            stats.api_requests_used = 2
            return stats
        if self.calls == 1:
            stats.created_issues = 3
            stats.updated_issues = 0
        else:
            stats.created_issues = 0
            stats.updated_issues = 3
        stats.api_requests_used = 4
        stats.imported_series = 1
        return stats


def _issue_count(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(CatalogIssue)).one())


def test_dry_run_does_not_update_queue_running(session: Session) -> None:
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=777,
            name="Absolute Batman",
            publisher="DC Comics",
            count_of_issues=12,
            existing_issue_count=0,
            missing_issue_count=12,
            coverage_percent=0.0,
            priority_score=1_000_000.0,
            launch_priority_tier="tier_0_manual_request",
            status=STATUS_PENDING,
        )
    )
    session.commit()
    budget = ComicVineRateBudget(session)
    importer = FakeImporter(dry_run=True)
    result = import_requested_volume_issues(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        volume_id=777,
        dry_run=True,
    )
    assert result.dry_run is True
    assert result.created_issues == 0
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 777
        )
    ).one()
    assert row.status == STATUS_PENDING
    assert _issue_count(session) == 0


def test_import_is_idempotent_for_importer_calls(session: Session) -> None:
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=888,
            name="Test Vol",
            publisher="DC Comics",
            count_of_issues=3,
            existing_issue_count=0,
            missing_issue_count=3,
            coverage_percent=0.0,
            priority_score=1_000_000.0,
            launch_priority_tier="tier_0_manual_request",
            status=STATUS_PENDING,
        )
    )
    session.commit()
    budget = ComicVineRateBudget(session)
    importer = FakeImporter()

    first = import_requested_volume_issues(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        volume_id=888,
        dry_run=False,
    )
    second = import_requested_volume_issues(
        session,
        budget,
        importer,  # type: ignore[arg-type]
        volume_id=888,
        dry_run=False,
    )
    assert first.created_issues == 3
    assert second.created_issues == 0
    assert second.updated_issues == 3
    assert importer.calls == 2
