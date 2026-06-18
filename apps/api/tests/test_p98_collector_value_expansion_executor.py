"""P98 collector-value expansion executor tests."""

from __future__ import annotations

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
from app.services.p98_collector_value_expansion_executor_service import (  # noqa: E402
    GROUP_A,
    GROUP_B,
    GROUP_C,
    execute_collector_expansion_plan,
    order_collector_volumes,
    parse_group_spec,
    top_collector_rank_map,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _seed_ec_harvey(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        ComicVineVolumeUniverse(
            volume_id=1,
            name="Vault of Horror",
            publisher="EC",
            count_of_issues=10,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=2,
            name="Big Harvey Run",
            publisher="Harvey",
            count_of_issues=50,
            first_discovered_at=now,
            last_discovered_at=now,
        )
    )
    for pub_name in ("EC", "Harvey"):
        pub = UniversePublisher(name=pub_name, normalized_name=pub_name.lower())
        session.add(pub)
    session.commit()
    for cv_id, name, pub_name, count in (
        (1, "Vault of Horror", "EC", 10),
        (2, "Big Harvey Run", "Harvey", 50),
    ):
        pub = session.exec(
            select(UniversePublisher).where(UniversePublisher.name == pub_name)
        ).one()
        session.add(
            UniverseVolume(
                comicvine_volume_id=cv_id,
                publisher_id=int(pub.id or 0),
                name=name,
                normalized_name=name.lower(),
                count_of_issues=count,
            )
        )
    session.commit()


def test_parse_group_spec() -> None:
    assert parse_group_spec("A,B") == [GROUP_A, GROUP_B]
    assert parse_group_spec("A,B,C") == [GROUP_A, GROUP_B, GROUP_C]
    assert parse_group_spec(None) == [GROUP_A, GROUP_B]


def test_collector_ranked_ec_before_harvey_mass() -> None:
    rows = [
        {
            "comicvine_volume_id": 2,
            "publisher": "Harvey",
            "collector_value_score": 60.0,
            "missing_shells": 50,
        },
        {
            "comicvine_volume_id": 1,
            "publisher": "EC",
            "collector_value_score": 90.0,
            "missing_shells": 10,
        },
    ]
    rank_map = top_collector_rank_map(
        [{"comicvine_volume_id": 1}, {"comicvine_volume_id": 2}]
    )
    ordered = order_collector_volumes(rows, collector_ranked=True, rank_map=rank_map)
    assert ordered[0]["comicvine_volume_id"] == 1


def test_dry_run_no_writes(session: Session) -> None:
    _seed_ec_harvey(session)
    from app.services.p98_collector_value_expansion_executor_service import (
        CollectorExpansionPlan,
        CollectorPlannedVolume,
    )

    plan = CollectorExpansionPlan(
            selected_groups=[GROUP_A],
            collector_ranked=False,
            volumes_selected=1,
            shells_to_create=5,
            projected_coverage_gain_percent=0.01,
            volumes=[
                CollectorPlannedVolume(
                    comicvine_volume_id=1,
                    volume_name="Vault of Horror",
                    publisher="EC",
                    execution_group=GROUP_A,
                    collector_value_score=90.0,
                    shells_to_create=5,
                    missing_shells=10,
                )
            ],
            dry_run=True,
        )

    result = execute_collector_expansion_plan(session, plan, dry_run=True)
    count = session.exec(select(func.count()).select_from(UniverseIssue)).one()
    assert count == 0
    assert result.stats.issues_created == 5


def test_apply_respects_max_via_plan(session: Session) -> None:
    _seed_ec_harvey(session)
    from app.services.p98_collector_value_expansion_executor_service import (
        CollectorExpansionPlan,
        CollectorPlannedVolume,
    )

    plan = CollectorExpansionPlan(
        selected_groups=[GROUP_A, GROUP_B],
        collector_ranked=True,
        volumes_selected=1,
        shells_to_create=3,
        projected_coverage_gain_percent=0.0,
        volumes=[
            CollectorPlannedVolume(
                comicvine_volume_id=1,
                volume_name="Vault of Horror",
                publisher="EC",
                execution_group=GROUP_A,
                collector_value_score=90.0,
                shells_to_create=3,
                missing_shells=10,
            )
        ],
        dry_run=False,
    )
    execute_collector_expansion_plan(session, plan, dry_run=False)
    count = session.exec(select(func.count()).select_from(UniverseIssue)).one()
    assert count == 3
