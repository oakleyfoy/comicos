"""P99 catalog acquisition gap service tests."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import P97VolumeIssueImportQueue  # noqa: E402
from app.models.universe import (  # noqa: E402
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UniverseIssue,
    UniversePublisher,
    UniverseVolume,
)
from app.services.p99_catalog_acquisition_gap_service import (  # noqa: E402
    CATEGORY_NOT_QUEUED,
    CATEGORY_QUEUED_PENDING,
    build_catalog_acquisition_gap_report,
    classify_gap_reason,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_classify_not_queued_vs_pending() -> None:
    assert classify_gap_reason(comicvine_issue_id=1, queue_row=None, import_errors_by_ext={}) == CATEGORY_NOT_QUEUED
    row = P97VolumeIssueImportQueue(
        comicvine_volume_id=10,
        name="Test",
        status="pending",
    )
    assert (
        classify_gap_reason(comicvine_issue_id=1, queue_row=row, import_errors_by_ext={})
        == CATEGORY_QUEUED_PENDING
    )


def test_report_counts_discovered_gap(session: Session) -> None:
    now = datetime.now(timezone.utc)
    pub = UniversePublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    vol = UniverseVolume(
        comicvine_volume_id=999,
        publisher_id=int(pub.id or 0),
        name="Amazing Spider-Man",
        normalized_name="amazing spider man",
        count_of_issues=2,
    )
    session.add(vol)
    session.commit()
    session.refresh(vol)
    session.add(
        UniverseIssue(
            volume_id=int(vol.id or 0),
            issue_number="1",
            normalized_issue_number="1",
            comicvine_issue_id=1001,
            status=UNIVERSE_ISSUE_STATUS_DISCOVERED,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    report = build_catalog_acquisition_gap_report(session, issue_sample_limit=10, top_volumes=10)
    assert report.global_summary["import_gap_universe_discovered"] == 1
    not_queued = next(r for r in report.gap_by_category if r["category"] == CATEGORY_NOT_QUEUED)
    assert not_queued["issue_count"] == 1
