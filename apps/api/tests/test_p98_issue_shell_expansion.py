"""P98 — issue shell expansion from discovered metadata."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.universe import UniverseIssue, UniverseVariant, UniverseVolume
from app.services.p98_issue_shell_expansion_service import (
    VOLUME_STATUS_SHELL_ONLY,
    build_expansion_report,
    default_progress_path,
    expand_action_queue,
    expand_volume_issue_shells,
    get_volume_expansion_candidates,
    load_progress,
    save_progress,
)
from app.services.p98_skeleton_gap_service import ACTION_BUILD_SHELLS, STATUS_SHELL_ONLY
from test_p98_skeleton_gap_service import seed_gap


def test_expansion_candidates_build_shells_only(client: TestClient, session: Session) -> None:
    seed_gap(session)
    rows = get_volume_expansion_candidates(session, publisher="Marvel", use_live_gap_queue=True)
    assert all(r.expected_issue_count > 0 for r in rows)
    # 88004 volume-only (10 expected), not 88001-88003 with issues
    cv_ids = {c.comicvine_volume_id for c in rows}
    assert 88004 in cv_ids
    assert 88001 not in cv_ids


def test_issue_numbers_generated(client: TestClient, session: Session) -> None:
    seed_gap(session)
    vol = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88004)).one()
    from app.services.p98_issue_shell_expansion_service import ExpansionStats

    stats = ExpansionStats()
    expand_volume_issue_shells(
        session,
        volume=vol,
        expected_issue_count=10,
        stats=stats,
        publisher_label="Marvel",
    )
    session.commit()
    issues = session.exec(
        select(UniverseIssue)
        .where(UniverseIssue.volume_id == int(vol.id or 0))
        .order_by(UniverseIssue.normalized_issue_number.asc())
    ).all()
    assert len(issues) == 10
    assert sorted(int(i.issue_number) for i in issues) == list(range(1, 11))
    assert stats.issues_created == 10
    assert stats.variants_created == 10
    for issue in issues:
        variants = session.exec(select(UniverseVariant).where(UniverseVariant.issue_id == issue.id)).all()
        assert len(variants) >= 1
        assert any(v.variant_type == "UNKNOWN" for v in variants)


def test_expansion_idempotent(client: TestClient, session: Session) -> None:
    seed_gap(session)
    vol = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88004)).one()
    from app.services.p98_issue_shell_expansion_service import ExpansionStats

    stats1 = ExpansionStats()
    expand_volume_issue_shells(session, volume=vol, expected_issue_count=10, stats=stats1, publisher_label="Marvel")
    session.commit()
    stats2 = ExpansionStats()
    expand_volume_issue_shells(session, volume=vol, expected_issue_count=10, stats=stats2, publisher_label="Marvel")
    session.commit()
    assert stats2.issues_created == 0
    assert stats2.variants_created == 0
    assert len(session.exec(select(UniverseIssue).where(UniverseIssue.volume_id == vol.id)).all()) == 10


def test_status_transitions_to_shell_only(client: TestClient, session: Session) -> None:
    seed_gap(session)
    vol = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88004)).one()
    from app.services.p98_issue_shell_expansion_service import ExpansionStats

    expand_volume_issue_shells(
        session,
        volume=vol,
        expected_issue_count=10,
        stats=ExpansionStats(),
        publisher_label="Marvel",
    )
    session.commit()
    session.refresh(vol)
    assert vol.volume_status == VOLUME_STATUS_SHELL_ONLY


def test_dry_run_no_mutation(client: TestClient, session: Session, tmp_path: Path) -> None:
    seed_gap(session)
    stats = expand_action_queue(
        session,
        publisher="Marvel",
        queue_path=tmp_path / "missing_queue.json",
        progress_path=tmp_path / "progress.json",
        dry_run=True,
        resume_from_progress=False,
        limit_volumes=1,
    )
    assert stats.volumes_selected >= 1
    vol = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88004)).one()
    assert (
        session.exec(select(UniverseIssue).where(UniverseIssue.volume_id == vol.id)).first() is None
    )


def test_apply_mutation(client: TestClient, session: Session, tmp_path: Path) -> None:
    seed_gap(session)
    before = len(session.exec(select(UniverseIssue)).all())
    stats = expand_action_queue(
        session,
        publisher="Marvel",
        limit_volumes=1,
        queue_path=tmp_path / "missing_queue.json",
        progress_path=tmp_path / "progress.json",
        dry_run=False,
        resume_from_progress=False,
        commit_every=1,
    )
    after = len(session.exec(select(UniverseIssue)).all())
    assert after > before
    assert stats.issues_created > 0
    assert stats.variants_created > 0


def test_resume_skips_completed(client: TestClient, session: Session, tmp_path: Path) -> None:
    seed_gap(session)
    progress_path = tmp_path / "progress.json"
    expand_action_queue(
        session,
        publisher="Marvel",
        limit_volumes=1,
        queue_path=tmp_path / "missing_queue.json",
        progress_path=progress_path,
        dry_run=False,
        resume_from_progress=False,
        commit_every=1,
    )
    prog = load_progress(progress_path)
    assert prog["completed_comicvine_volume_ids"]
    stats2 = expand_action_queue(
        session,
        publisher="Marvel",
        limit_volumes=5,
        progress_path=progress_path,
        dry_run=False,
        resume_from_progress=True,
        commit_every=1,
    )
    assert stats2.volumes_expanded == 0 or stats2.volumes_skipped >= 1


def test_expansion_report_counts(client: TestClient, session: Session, tmp_path: Path) -> None:
    seed_gap(session)
    report = build_expansion_report(session, queue_path=tmp_path / "no_queue.json")
    assert report.remaining_build_shells_volumes >= 1
    assert report.projected_gain >= 10
