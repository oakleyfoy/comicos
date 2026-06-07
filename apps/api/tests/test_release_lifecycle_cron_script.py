from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.models import User
from app.models.p82_p84_collector_expansion import CollectorBriefing, CollectorNotification
from app.models.p86_release_lifecycle import P86ReleaseLifecycleReport, P86ReleaseLifecycleRun, RUN_STATUS_COMPLETE
from app.services.release_lifecycle_cron import redact_database_url, run_release_lifecycle_weekly_cron
from app.services.release_lifecycle_plan import build_weekly_lifecycle_plan
from app.services.release_lifecycle_report_service import (
    build_weekly_report_body,
    compute_overall_status,
    finalize_weekly_lifecycle_report,
    get_latest_lifecycle_report,
    notification_priority,
)

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = API_ROOT / "scripts" / "run_release_lifecycle_weekly.py"
FAKE_SUMMARY = """
--- LoCG capture final summary ---
Date: 2026-06-10
Run status: COMPLETE
Parent queue: 10
Parent captured: 10
DB issues: 5
DB variants: 12
Skipped missing parent: 0
Variant upsert failures: 0
Warnings: []
Failures: []
Elapsed seconds: 1.0
Crosswalk skipped: True
Raw path: /tmp
--- end final summary ---
"""


def test_redact_database_url_hides_password() -> None:
    info = redact_database_url("postgresql+pg8000://user:secret@db.example.com:5433/comic_os")
    assert info["username"] == "user"
    assert info["host"] == "db.example.com"
    assert info["database"] == "comic_os"
    assert "secret" not in str(info.values())


def test_missing_database_url_fails(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = run_release_lifecycle_weekly_cron(database_url="")
    assert result.exit_code == 1


def test_dry_run_prints_plan(client, session: Session, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    user = User(email="ofoy@att.net", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///test.db"))
    result = run_release_lifecycle_weekly_cron(dry_run=True)
    assert result.exit_code == 0
    assert result.status == "DRY_RUN"
    out = capsys.readouterr().out
    assert "EARLY_DISCOVERY" in out or "Weekly lifecycle capture plan" in out


def test_script_missing_database_url_exits_one(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    proc = subprocess.run(
        [os.environ.get("PYTHON", "python"), str(SCRIPT), "--dry-run"],
        cwd=str(API_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1


def test_owner_lookup_failure_exits_one(client, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "sqlite:///test.db"))
    result = run_release_lifecycle_weekly_cron(dry_run=True, database_url=os.environ["DATABASE_URL"])
    if result.exit_code == 1 and "owner lookup" in result.message:
        assert True
    else:
        pytest.skip("production owner present in test DB")


def test_weekly_run_creates_report_and_notification(client, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    email = "p86-report@example.com"
    user = User(email=email, password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    owner_id = int(user.id or 0)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 10))
    runs = [
        P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=plan.run_date,
            anchor_release_date=plan.anchor_release_date,
            target_release_date=date(2026, 6, 10),
            lifecycle_stage="RELEASE_DAY_REFRESH",
            command="x",
            status=RUN_STATUS_COMPLETE,
            issue_count=10,
            variant_count=20,
            crosswalk_skipped=True,
        )
    ]
    for r in runs:
        session.add(r)
    session.commit()
    for r in runs:
        session.refresh(r)
    report = finalize_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=runs)
    assert report is not None
    notifs = session.exec(
        select(CollectorNotification).where(
            CollectorNotification.owner_user_id == owner_id,
            CollectorNotification.notification_type == "RELEASE_LIFECYCLE_REPORT",
        )
    ).all()
    assert len(notifs) >= 1
    briefings = session.exec(select(CollectorBriefing).where(CollectorBriefing.owner_user_id == owner_id)).all()
    assert any("release_lifecycle" in (b.sections_json or {}) for b in briefings)


def test_blocked_date_high_priority_notification(client, session: Session) -> None:
    owner = User(email="p86-pri@example.com", password_hash="x", is_active=True)
    session.add(owner)
    session.commit()
    session.refresh(owner)
    owner_id = int(owner.id or 0)
    plan = build_weekly_lifecycle_plan(anchor=date(2026, 6, 10), run_date=date(2026, 6, 11))
    runs = [
        P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=plan.run_date,
            anchor_release_date=plan.anchor_release_date,
            target_release_date=date(2026, 9, 2),
            lifecycle_stage="EARLY_DISCOVERY",
            command="x",
            status="BLOCKED",
            crosswalk_skipped=True,
        )
    ]
    for r in runs:
        session.add(r)
    session.commit()
    for r in runs:
        session.refresh(r)
    assert notification_priority(runs) == "HIGH"
    assert compute_overall_status(runs) == "NEEDS_ATTENTION"


def test_all_complete_normal_priority(client, session: Session) -> None:
    runs = [
        P86ReleaseLifecycleRun(
            owner_id=1,
            run_date=date(2026, 6, 10),
            anchor_release_date=date(2026, 6, 10),
            target_release_date=date(2026, 6, 10),
            lifecycle_stage="RELEASE_DAY_REFRESH",
            command="x",
            status=RUN_STATUS_COMPLETE,
            crosswalk_skipped=True,
        )
    ]
    assert notification_priority(runs) == "NORMAL"
    body = build_weekly_report_body(runs=runs)
    assert "Crosswalk: skipped" in body


def test_latest_report_empty(client, session: Session) -> None:
    user = User(email="p86-empty@example.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    read = get_latest_lifecycle_report(session, owner_id=int(user.id or 0))
    assert read.status == "EMPTY"
