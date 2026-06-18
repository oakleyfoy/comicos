"""P99 pending queue drain planner tests."""

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
from app.services.p99_pending_queue_drain_service import (  # noqa: E402
    GROUP_1_MAJOR_CORE,
    GROUP_4_FOREIGN_OR_LOW_PRIORITY,
    build_pending_queue_drain_plan,
    classify_drain_group,
    compute_drain_score,
)


def test_classify_major_core() -> None:
    assert classify_drain_group("Marvel") == GROUP_1_MAJOR_CORE
    assert classify_drain_group("Egmont Comics") == GROUP_4_FOREIGN_OR_LOW_PRIORITY


def test_drain_score_major_beats_foreign() -> None:
    major = compute_drain_score(
        drain_group=GROUP_1_MAJOR_CORE,
        publisher="Marvel",
        volume_name="Amazing Spider-Man",
        missing_issue_count=100,
        shells_without_catalog=80,
        queue_priority_score=120_000.0,
        start_year=1963,
    )
    foreign = compute_drain_score(
        drain_group=GROUP_4_FOREIGN_OR_LOW_PRIORITY,
        publisher="Egmont Comics",
        volume_name="Local Run",
        missing_issue_count=500,
        shells_without_catalog=500,
        queue_priority_score=120_000.0,
        start_year=1990,
    )
    assert major > foreign


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_plan_counts_pending_rows(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=100,
            name="Test Vol",
            publisher="Marvel",
            count_of_issues=10,
            missing_issue_count=10,
            status="pending",
            priority_score=50_000.0,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    plan = build_pending_queue_drain_plan(session, top_n=10)
    assert plan.summary["pending_queue_rows"] == 1
    assert plan.top_volumes[0].drain_group == GROUP_1_MAJOR_CORE
