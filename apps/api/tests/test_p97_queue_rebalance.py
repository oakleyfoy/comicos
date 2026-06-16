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

from app.models.catalog_p97 import P97VolumeIssueImportQueue
from app.services.p97_queue_priority_config import (
    CORE_RUN_BONUS,
    FOREIGN_ARCHIVE_PUBLISHER_WEIGHT,
    MISSING_ISSUE_BONUS_MULTIPLIER,
    RUN_SIZE_BONUS_MULTIPLIER,
    compute_collector_queue_score,
    is_core_run,
    resolve_collector_popularity_weight,
    resolve_core_run_bonus,
    resolve_missing_issue_bonus,
    resolve_publisher_weight,
    resolve_recent_year_bonus,
    resolve_run_size_bonus,
)
from app.services.p97_queue_rebalance_service import (
    apply_queue_rebalance,
    build_rebalance_comparison,
    compute_rebalance_score_for_row,
)
from app.services.p97_volume_issue_queue_priority import (
    TIER_0_MANUAL,
    compute_volume_import_priority,
)


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_publisher_weighting_marvel_dc_highest() -> None:
    assert resolve_publisher_weight("Marvel") == 100
    assert resolve_publisher_weight("DC Comics") == 100
    assert resolve_publisher_weight("Image") == 90
    assert resolve_publisher_weight("Random Indie") == 40


def test_core_run_detection_exact_only() -> None:
    assert is_core_run("Batman")
    assert is_core_run("Batman (1940)")
    assert is_core_run("Amazing Spider-Man (1963)")
    assert is_core_run("Uncanny X-Men")
    assert is_core_run("Uncanny X-Men (1963)")
    assert not is_core_run("Batman: Hong Kong")
    assert not is_core_run("Batman/Lobo")
    assert not is_core_run("Batman Annual")
    assert not is_core_run("X-Men 2099 Oasis")
    assert not is_core_run("X-Men 2099 A.D. Special")
    assert not is_core_run("Ultimate X-Men Annual")


def test_core_run_bonus_applied() -> None:
    assert resolve_core_run_bonus("Detective Comics") == CORE_RUN_BONUS
    assert resolve_core_run_bonus("Action Comics") == CORE_RUN_BONUS
    assert resolve_core_run_bonus("Batman: Year One") == 0


def test_collector_popularity_only_on_core_runs() -> None:
    assert resolve_collector_popularity_weight("Batman") == 500
    assert resolve_collector_popularity_weight("Batman: Hong Kong") == 0
    assert resolve_collector_popularity_weight("X-Men 2099 Oasis") == 0


def test_year_bonus_bands() -> None:
    assert resolve_recent_year_bonus(2024) == 1000
    assert resolve_recent_year_bonus(2015) == 500
    assert resolve_recent_year_bonus(2005) == 250
    assert resolve_recent_year_bonus(1999) == 0
    assert resolve_recent_year_bonus(None) == 0


def test_run_size_bonus_dominates_small_runs() -> None:
    assert resolve_run_size_bonus(716) == 716 * RUN_SIZE_BONUS_MULTIPLIER
    assert resolve_run_size_bonus(1) == RUN_SIZE_BONUS_MULTIPLIER
    assert resolve_run_size_bonus(2000) == 1000 * RUN_SIZE_BONUS_MULTIPLIER


def test_missing_issue_bonus_dominates() -> None:
    assert resolve_missing_issue_bonus(716) == 716 * MISSING_ISSUE_BONUS_MULTIPLIER
    assert resolve_missing_issue_bonus(1) == MISSING_ISSUE_BONUS_MULTIPLIER
    assert resolve_missing_issue_bonus(716) > resolve_missing_issue_bonus(1) * 100


def test_batman_beats_batman_hong_kong() -> None:
    ongoing = compute_collector_queue_score(
        publisher="DC Comics",
        name="Batman",
        missing_issue_count=716,
        total_issue_count=900,
    )
    one_shot = compute_collector_queue_score(
        publisher="DC Comics",
        name="Batman: Hong Kong",
        missing_issue_count=1,
        total_issue_count=1,
    )
    assert ongoing > one_shot


def test_batman_beats_batman_annual() -> None:
    ongoing = compute_collector_queue_score(
        publisher="DC Comics",
        name="Batman",
        missing_issue_count=500,
        total_issue_count=800,
    )
    annual = compute_collector_queue_score(
        publisher="DC Comics",
        name="Batman Annual",
        missing_issue_count=12,
        total_issue_count=12,
    )
    assert ongoing > annual


def test_amazing_spider_man_beats_super_special() -> None:
    flagship = compute_collector_queue_score(
        publisher="Marvel",
        name="The Amazing Spider-Man",
        missing_issue_count=651,
        total_issue_count=900,
    )
    special = compute_collector_queue_score(
        publisher="Marvel",
        name="Amazing Spider-Man Super Special",
        missing_issue_count=1,
        total_issue_count=1,
    )
    assert flagship > special


def test_foreign_publishers_deprioritized() -> None:
    assert resolve_publisher_weight("Rebellion") == FOREIGN_ARCHIVE_PUBLISHER_WEIGHT
    foreign_score = compute_collector_queue_score(
        publisher="Rebellion",
        name="2000 AD",
        missing_issue_count=500,
        total_issue_count=500,
    )
    core_score = compute_collector_queue_score(
        publisher="DC Comics",
        name="Detective Comics",
        missing_issue_count=25,
        total_issue_count=900,
    )
    assert core_score > foreign_score


def test_collector_score_formula_components() -> None:
    score = compute_collector_queue_score(
        publisher="Marvel",
        name="Venom",
        missing_issue_count=10,
        total_issue_count=120,
        start_year=2022,
    )
    expected = (
        100 * 100_000
        + 500 * 1_000
        + CORE_RUN_BONUS
        + 10 * MISSING_ISSUE_BONUS_MULTIPLIER
        + min(120, 1000) * RUN_SIZE_BONUS_MULTIPLIER
        + 1_000
    )
    assert score == float(expected)


def test_ranking_changes_core_above_obscure() -> None:
    obscure = compute_volume_import_priority(
        missing_issue_count=200,
        count_of_issues=200,
        coverage_percent=0.0,
        publisher="Unknown",
        name="Mnemovore",
    )
    batman = compute_volume_import_priority(
        missing_issue_count=50,
        count_of_issues=900,
        coverage_percent=5.0,
        publisher="DC Comics",
        name="Batman",
        start_year=2020,
    )
    assert batman.priority_score > obscure.priority_score


def test_queue_rows_preserved_on_dry_run_apply(session: Session) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        P97VolumeIssueImportQueue(
            comicvine_volume_id=900001,
            name="Batman",
            publisher="DC Comics",
            count_of_issues=100,
            existing_issue_count=50,
            missing_issue_count=50,
            coverage_percent=50.0,
            priority_score=1.0,
            launch_priority_tier="tier_1_core",
            status="pending",
            created_at=now,
            updated_at=now,
        ),
        P97VolumeIssueImportQueue(
            comicvine_volume_id=900002,
            name="Mnemovore",
            publisher="Small Press",
            count_of_issues=12,
            existing_issue_count=0,
            missing_issue_count=12,
            coverage_percent=0.0,
            priority_score=9_999_999.0,
            launch_priority_tier="tier_3_other_us",
            status="pending",
            created_at=now,
            updated_at=now,
        ),
    ]
    for row in rows:
        session.add(row)
    session.commit()

    before = session.exec(select(P97VolumeIssueImportQueue)).all()
    result = apply_queue_rebalance(session, dry_run=True)
    after = session.exec(select(P97VolumeIssueImportQueue)).all()
    assert len(before) == len(after) == 2
    assert result.row_count_before == result.row_count_after == 2
    assert result.rows_updated >= 1
    assert float(before[1].priority_score) == 9_999_999.0


def test_apply_updates_scores_not_row_count(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=900003,
            name="The Amazing Spider-Man",
            publisher="Marvel",
            count_of_issues=80,
            existing_issue_count=40,
            missing_issue_count=40,
            coverage_percent=50.0,
            priority_score=100.0,
            launch_priority_tier="tier_1_core",
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    apply_queue_rebalance(session, dry_run=False)
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 900003
        )
    ).one()
    expected = compute_rebalance_score_for_row(row)
    assert row.priority_score == expected
    assert row.priority_score > 100.0


def test_manual_tier_skipped_on_apply(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=900004,
            name="Manual Request",
            publisher="Marvel",
            count_of_issues=5,
            existing_issue_count=0,
            missing_issue_count=5,
            coverage_percent=0.0,
            priority_score=2_000_000.0,
            launch_priority_tier=TIER_0_MANUAL,
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    result = apply_queue_rebalance(session, dry_run=False)
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.comicvine_volume_id == 900004
        )
    ).one()
    assert row.priority_score == 2_000_000.0
    assert result.rows_skipped_manual == 1


def test_build_rebalance_comparison_ranks(session: Session) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=900005,
            name="Batman",
            publisher="DC Comics",
            count_of_issues=100,
            existing_issue_count=90,
            missing_issue_count=10,
            coverage_percent=90.0,
            priority_score=50.0,
            launch_priority_tier="tier_1_core",
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=900006,
            name="Obscure",
            publisher="Unknown",
            count_of_issues=500,
            existing_issue_count=0,
            missing_issue_count=500,
            coverage_percent=0.0,
            priority_score=99_999_999.0,
            launch_priority_tier="tier_3_other_us",
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()

    report = build_rebalance_comparison(session)
    assert report.eligible_row_count == 2
    rebalanced_names = [e.name for e in report.rebalanced_top_100]
    assert rebalanced_names[0] == "Batman"
    assert report.coverage_gain_potential >= 500
