from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from app.models import User
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from app.services.release_lifecycle_scheduler import (
    ReleaseLifecycleStopError,
    build_capture_argv,
    is_playwright_launch_failure,
    run_weekly_lifecycle_batch,
    verify_owner_lookup,
)
import subprocess


def test_owner_lookup_failure_stops_batch(client, session: Session) -> None:
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    with pytest.raises(ReleaseLifecycleStopError):
        run_weekly_lifecycle_batch(
            session,
            database_url="sqlite://",
            owner_email="no-such-owner@example.com",
            plan=plan,
        )


def test_playwright_launch_failure_detection() -> None:
    assert is_playwright_launch_failure(stderr="playwright install chromium", stdout="")
    assert is_playwright_launch_failure(stderr="Failed to launch browser", stdout="playwright")


def test_consecutive_blocked_stops_after_two(client, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(email="p86-stop@example.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 13))
    blocked = """
--- LoCG capture final summary ---
Date: 2026-06-10
Run status: BLOCKED
Parent queue: 0
Parent captured: 0
DB issues: 0
DB variants: 0
Skipped missing parent: 0
Variant upsert failures: 0
Warnings: []
Failures: ['cloudflare']
Elapsed seconds: 1.0
Crosswalk skipped: True
Raw path: /
--- end final summary ---
"""

    def _runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, blocked, "cloudflare blocked")

    monkeypatch.setattr(
        "app.services.release_lifecycle_scheduler.run_post_weekly_refreshes",
        lambda *a, **k: None,
    )
    runs = run_weekly_lifecycle_batch(
        session,
        database_url="sqlite://",
        owner_email="p86-stop@example.com",
        plan=plan,
        runner=_runner,
    )
    assert len(runs) == 2


def test_capture_never_includes_run_crosswalk() -> None:
    argv = build_capture_argv(capture_date=date(2026, 6, 10))
    assert "--skip-crosswalk" in argv
    assert "--run-crosswalk" not in argv


def test_verify_owner_lookup_success(client, session: Session) -> None:
    user = User(email="p86-owner@example.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    assert verify_owner_lookup(session, email="p86-owner@example.com") == int(user.id or 0)
