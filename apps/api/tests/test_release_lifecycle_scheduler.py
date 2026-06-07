from __future__ import annotations

import subprocess
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p86_release_lifecycle import (
    P86ReleaseLifecycleRun,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_COMPLETE,
    RUN_STATUS_RUNNING,
)
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from app.services.release_lifecycle_scheduler import (
    ReleaseLifecycleStopError,
    build_capture_argv,
    has_active_lifecycle_runs,
    parse_capture_summary,
    run_weekly_lifecycle_batch,
    verify_owner_lookup,
)

FAKE_SUMMARY = """
--- LoCG capture final summary ---
Date: 2026-06-10
Run status: COMPLETE
Parent queue: 100
Parent captured: 100
DB issues: 95
DB variants: 300
Skipped missing parent: 0
Variant upsert failures: 0
Warnings: []
Failures: []
Elapsed seconds: 120.5
Crosswalk skipped: True
Raw path: /data/locg_browser_capture/2026-06-10
--- end final summary ---
"""


def _register_user(session: Session, email: str) -> int:
    user = User(email=email, password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return int(user.id or 0)


def test_capture_argv_includes_skip_crosswalk_and_production() -> None:
    argv = build_capture_argv(capture_date=date(2026, 6, 10))
    assert "--skip-crosswalk" in argv
    assert "--production" in argv
    assert "--run-crosswalk" not in argv
    assert "2026-06-10" in argv


def test_parse_capture_summary() -> None:
    parsed = parse_capture_summary(FAKE_SUMMARY)
    assert parsed["Run status"] == "COMPLETE"
    assert parsed["DB issues"] == "95"
    assert parsed["Crosswalk skipped"] == "True"


def test_verify_owner_lookup_failure(client, session: Session) -> None:
    with pytest.raises(ReleaseLifecycleStopError):
        verify_owner_lookup(session, email="missing-owner@example.com")


def test_sequential_weekly_batch_persists_runs(client, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    owner_id = _register_user(session, "p86-sched@example.com")
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    call_count = {"n": 0}

    def _fake_runner(argv, **kwargs):
        call_count["n"] += 1
        return subprocess.CompletedProcess(argv, 0, FAKE_SUMMARY, "")

    monkeypatch.setattr(
        "app.services.release_lifecycle_scheduler.run_post_weekly_refreshes",
        lambda *a, **k: None,
    )

    runs = run_weekly_lifecycle_batch(
        session,
        database_url="sqlite://",
        owner_email="p86-sched@example.com",
        plan=plan,
        runner=_fake_runner,
    )
    assert len(runs) == 4
    assert call_count["n"] == 4
    assert all(r.status == RUN_STATUS_COMPLETE for r in runs)
    assert all(r.crosswalk_skipped for r in runs)
    rows = session.exec(select(P86ReleaseLifecycleRun).where(P86ReleaseLifecycleRun.owner_id == owner_id)).all()
    assert len(rows) == 4


def test_duplicate_active_job_prevented(client, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _register_user(session, "p86-dup@example.com")
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 11))
    session.add(
        P86ReleaseLifecycleRun(
            owner_id=int(session.exec(select(User).where(User.email == "p86-dup@example.com")).one().id or 0),
            run_date=plan.run_date,
            anchor_release_date=plan.anchor_release_date,
            target_release_date=date(2026, 6, 10),
            lifecycle_stage="RELEASE_DAY_REFRESH",
            command="test",
            status=RUN_STATUS_RUNNING,
        )
    )
    session.commit()
    assert has_active_lifecycle_runs(session, owner_id=int(session.exec(select(User).where(User.email == "p86-dup@example.com")).one().id or 0))
    runs = run_weekly_lifecycle_batch(
        session,
        database_url="sqlite://",
        owner_email="p86-dup@example.com",
        plan=plan,
        runner=lambda *a, **k: subprocess.CompletedProcess([], 0, FAKE_SUMMARY, ""),
    )
    assert runs == []


def test_blocked_date_does_not_stop_entire_batch(client, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    _register_user(session, "p86-block@example.com")
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 12))
    responses = [
        FAKE_SUMMARY,
        FAKE_SUMMARY.replace("Run status: COMPLETE", "Run status: BLOCKED"),
        FAKE_SUMMARY,
        FAKE_SUMMARY,
    ]

    def _runner(argv, **kwargs):
        body = responses.pop(0)
        return subprocess.CompletedProcess(argv, 1, body, "cloudflare block")

    monkeypatch.setattr(
        "app.services.release_lifecycle_scheduler.run_post_weekly_refreshes",
        lambda *a, **k: None,
    )
    runs = run_weekly_lifecycle_batch(
        session,
        database_url="sqlite://",
        owner_email="p86-block@example.com",
        plan=plan,
        runner=_runner,
    )
    assert len(runs) == 4
    assert runs[1].status == RUN_STATUS_BLOCKED
    assert runs[0].status == RUN_STATUS_COMPLETE
