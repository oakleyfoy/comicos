"""P97 queue repair plan and apply tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, func, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue  # noqa: E402
from app.services.p97_queue_repair_service import (  # noqa: E402
    ACTION_ADD_TO_P97_QUEUE,
    ACTION_SKIP_COMPLETE,
    ACTION_SKIP_LOW_VALUE,
    apply_queue_repair_plan,
    build_queue_repair_plan,
    load_queue_repair_plan,
    save_queue_repair_plan,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_plan_add_to_queue_for_gap_only(session: Session, tmp_path: Path) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=500,
            name="Gap Volume",
            publisher="Marvel",
            count_of_issues=40,
        )
    )
    session.commit()
    plan = build_queue_repair_plan(session)
    add_rows = [r for r in plan if r.recommended_action == ACTION_ADD_TO_P97_QUEUE]
    assert any(r.comicvine_volume_id == 500 for r in add_rows)
    low = [r for r in plan if r.recommended_action == ACTION_SKIP_LOW_VALUE]
    session.add(
        ComicVineVolumeUniverse(
            volume_id=501,
            name="Tiny Obscure",
            publisher="Marvel",
            count_of_issues=2,
        )
    )
    session.commit()
    plan2 = build_queue_repair_plan(session)
    assert any(r.comicvine_volume_id == 501 and r.recommended_action == ACTION_SKIP_LOW_VALUE for r in plan2)


def test_complete_universe_not_in_plan(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=600,
            name="Fully Cataloged",
            publisher="Marvel",
            count_of_issues=0,
        )
    )
    session.commit()
    plan = build_queue_repair_plan(session)
    assert not any(r.comicvine_volume_id == 600 for r in plan)


def test_apply_dry_run_does_not_mutate(session: Session, tmp_path: Path) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=700,
            name="Needs Queue",
            publisher="Marvel",
            count_of_issues=15,
        )
    )
    session.commit()
    plan = build_queue_repair_plan(session)
    plan = [r for r in plan if r.comicvine_volume_id == 700 and r.recommended_action == ACTION_ADD_TO_P97_QUEUE]
    assert plan
    before = session.exec(select(func.count()).select_from(P97VolumeIssueImportQueue)).one()
    result = apply_queue_repair_plan(session, plan, dry_run=True)
    after = session.exec(select(func.count()).select_from(P97VolumeIssueImportQueue)).one()
    assert before == after == 0
    assert result.would_add >= 1


def test_apply_inserts_with_apply_flag(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=800,
            name="Apply Me",
            publisher="Marvel",
            count_of_issues=8,
        )
    )
    session.commit()
    plan = [
        row
        for row in build_queue_repair_plan(session)
        if row.comicvine_volume_id == 800 and row.recommended_action == ACTION_ADD_TO_P97_QUEUE
    ]
    assert plan
    result = apply_queue_repair_plan(session, plan, dry_run=False)
    assert result.added == 1
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.comicvine_volume_id == 800)
    ).one()
    assert row.missing_issue_count == 8
    assert row.status == "pending"


def test_save_and_load_plan(tmp_path: Path) -> None:
    from app.services.p97_queue_repair_service import QueueRepairPlanRow

    path = tmp_path / "plan.json"
    rows = [
        QueueRepairPlanRow(
            comicvine_volume_id=1,
            name="X",
            publisher="Marvel",
            missing_issue_count=10,
            recommended_action=ACTION_ADD_TO_P97_QUEUE,
        )
    ]
    save_queue_repair_plan(rows, path=path)
    loaded = load_queue_repair_plan(path)
    assert len(loaded) == 1
    assert loaded[0].comicvine_volume_id == 1
