"""P98 major publisher completeness report tests."""

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

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue  # noqa: E402
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVolume  # noqa: E402
from app.services.p98_major_publisher_completeness_service import (  # noqa: E402
    build_major_publisher_completeness_report,
)
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_completeness_metrics(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        ComicVineVolumeUniverse(
            volume_id=1,
            name="Amazing Spider-Man",
            publisher="Marvel",
            count_of_issues=100,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=2,
            name="Flash",
            publisher="ECC Ediciones",
            count_of_issues=50,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    pub = UniversePublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    uv = UniverseVolume(
        comicvine_volume_id=1,
        publisher_id=int(pub.id or 0),
        name="Amazing Spider-Man",
        normalized_name="amazing spider man",
        count_of_issues=100,
    )
    session.add(uv)
    session.flush()
    for i in range(1, 81):
        session.add(
            UniverseIssue(
                volume_id=int(uv.id or 0),
                issue_number=str(i),
                normalized_issue_number=str(i),
                status="DISCOVERED",
            )
        )
    session.add(
        UniverseVolume(
            comicvine_volume_id=2,
            publisher_id=int(pub.id or 0),
            name="Flash",
            normalized_name="flash",
            volume_status=VOLUME_STATUS_FOREIGN_SUPERSEDED,
        )
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=1,
            name="Amazing Spider-Man",
            publisher="Marvel",
            count_of_issues=100,
            existing_issue_count=0,
            missing_issue_count=20,
            coverage_percent=0.0,
            priority_score=1.0,
            launch_priority_tier="tier_1_core",
            status="pending",
        )
    )
    session.commit()

    report = build_major_publisher_completeness_report(
        session, include_optional=False, top_missing_per_publisher=5
    )
    marvel = next(p for p in report.publishers if p.publisher == "Marvel")
    assert marvel.comicvine_universe_volumes == 1
    assert marvel.canonical_p98_volumes == 1
    assert marvel.issue_shells_built == 80
    assert marvel.missing_issue_shells == 20
    assert marvel.queued_missing_issues == 20
    assert marvel.coverage_percent == 80.0
