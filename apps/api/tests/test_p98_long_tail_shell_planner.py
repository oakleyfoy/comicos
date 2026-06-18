"""P98 long-tail shell planner tests."""

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

from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVolume  # noqa: E402
from app.services.p98_long_tail_shell_planner_service import (  # noqa: E402
    TIER_1_LABEL,
    TIER_4_LABEL,
    build_long_tail_shell_planner_report,
    classify_publisher_tier,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_tier_classification() -> None:
    assert classify_publisher_tier("Marvel") == TIER_1_LABEL
    assert classify_publisher_tier("ECC Ediciones") == TIER_4_LABEL


def test_planner_ranks_long_tail(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        ComicVineVolumeUniverse(
            volume_id=1,
            name="Marvel Tales",
            publisher="Marvel",
            count_of_issues=10,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=2,
            name="Long Run",
            publisher="Charlton Comics",
            count_of_issues=500,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    pub = UniversePublisher(name="Charlton Comics", normalized_name="charlton comics")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    uv = UniverseVolume(
        comicvine_volume_id=2,
        publisher_id=int(pub.id or 0),
        name="Long Run",
        normalized_name="long run",
        count_of_issues=500,
    )
    session.add(uv)
    session.flush()
    session.add(
        UniverseIssue(
            volume_id=int(uv.id or 0),
            issue_number="1",
            normalized_issue_number="1",
            status="DISCOVERED",
        )
    )
    session.commit()

    report = build_long_tail_shell_planner_report(session, top_publishers=10, top_volumes=10)
    charlton = next(p for p in report.publishers if p.publisher == "Charlton Comics")
    assert charlton.missing_shells == 499
    assert report.top_expansion_publishers[0].publisher == "Charlton Comics"
    assert report.scenarios[0].expected_shell_gain > 0
