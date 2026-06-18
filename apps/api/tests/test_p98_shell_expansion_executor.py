"""P98 shell expansion executor tests."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, func, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVolume  # noqa: E402
from app.services.p98_long_tail_shell_planner_service import TIER_2_LABEL, TIER_4_LABEL  # noqa: E402
from app.services.p98_shell_expansion_executor_service import (  # noqa: E402
    build_shell_expansion_plan,
    execute_shell_expansion_plan,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_charlton(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        ComicVineVolumeUniverse(
            volume_id=100,
            name="Long Run",
            publisher="Charlton",
            count_of_issues=50,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    pub = UniversePublisher(name="Charlton", normalized_name="charlton")
    session.add(pub)
    session.commit()
    session.refresh(pub)
    session.add(
        UniverseVolume(
            comicvine_volume_id=100,
            publisher_id=int(pub.id or 0),
            name="Long Run",
            normalized_name="long run",
            count_of_issues=50,
        )
    )
    session.commit()


def test_dry_run_does_not_create_shells(session: Session) -> None:
    _seed_charlton(session)
    rows = [
        {
            "comicvine_volume_id": 100,
            "volume": "Long Run",
            "publisher": "Charlton",
            "missing_shells": 50,
            "priority_tier": TIER_2_LABEL,
            "has_canonical_p98_volume": True,
        }
    ]
    plan = build_shell_expansion_plan(session, volume_rows=rows, max_shells=10, dry_run=True)
    assert plan.shells_to_create == 10
    result = execute_shell_expansion_plan(session, plan, dry_run=True)
    count = session.exec(select(func.count()).select_from(UniverseIssue)).one()
    assert count == 0
    assert result.stats.issues_created == 10


def test_apply_respects_max_shells(session: Session) -> None:
    _seed_charlton(session)
    rows = [
        {
            "comicvine_volume_id": 100,
            "volume": "Long Run",
            "publisher": "Charlton",
            "missing_shells": 50,
            "priority_tier": TIER_2_LABEL,
            "has_canonical_p98_volume": True,
        }
    ]
    plan = build_shell_expansion_plan(session, volume_rows=rows, max_shells=5)
    execute_shell_expansion_plan(session, plan, dry_run=False)
    count = session.exec(select(func.count()).select_from(UniverseIssue)).one()
    assert count == 5


def test_tier4_excluded_by_default(session: Session) -> None:
    _seed_charlton(session)
    rows = [
        {
            "comicvine_volume_id": 100,
            "volume": "Long Run",
            "publisher": "Charlton",
            "missing_shells": 50,
            "priority_tier": TIER_4_LABEL,
            "tier": 4,
            "priority": "LOW",
            "has_canonical_p98_volume": True,
        }
    ]
    plan = build_shell_expansion_plan(session, volume_rows=rows)
    assert plan.volumes_selected == 0
