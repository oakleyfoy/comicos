"""Shared weekly lifecycle cron entry (script + RQ)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable
from urllib.parse import unquote, urlparse

import subprocess
from sqlmodel import Session

from app.db.session import get_engine
from app.models.p86_release_lifecycle import P86ReleaseLifecycleReport
from app.services.release_lifecycle_plan import PRODUCTION_OWNER_EMAIL, build_weekly_lifecycle_plan
from app.services.release_lifecycle_report_service import finalize_weekly_lifecycle_report
from app.services.release_lifecycle_scheduler import (
    ReleaseLifecycleStopError,
    run_weekly_lifecycle_batch,
    verify_database_available,
    verify_owner_lookup,
)


@dataclass
class WeeklyLifecycleCronResult:
    exit_code: int
    status: str
    message: str
    runs: int
    report_id: int | None = None
    plan_printed: bool = False


def redact_database_url(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url.strip())
    host = parsed.hostname or ""
    database = (parsed.path or "").lstrip("/") or ""
    username = unquote(parsed.username or "")
    scheme = parsed.scheme or ""
    return {
        "scheme": scheme,
        "host": host,
        "database": database,
        "username": username,
    }


def print_database_target(database_url: str) -> None:
    info = redact_database_url(database_url)
    print(
        f"Database target: scheme={info['scheme']} host={info['host']} "
        f"database={info['database']} username={info['username']}",
        flush=True,
    )


def print_weekly_plan(*, anchor=None, run_date=None) -> None:
    plan = build_weekly_lifecycle_plan(anchor=anchor, run_date=run_date)
    print(f"Anchor release Wednesday (T): {plan.anchor_release_date.isoformat()}", flush=True)
    print("Weekly lifecycle capture plan:", flush=True)
    for item in plan.items:
        print(
            f"  {item.target_release_date.isoformat()} — {item.lifecycle_stage}",
            flush=True,
        )


def run_release_lifecycle_weekly_cron(
    *,
    database_url: str | None = None,
    dry_run: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> WeeklyLifecycleCronResult:
    db = (database_url or os.environ.get("DATABASE_URL", "")).strip()
    if not db:
        return WeeklyLifecycleCronResult(exit_code=1, status="FAILED", message="DATABASE_URL required", runs=0)

    print_database_target(db)

    with Session(get_engine()) as session:
        try:
            verify_database_available(session)
            owner_id = verify_owner_lookup(session, email=PRODUCTION_OWNER_EMAIL)
        except ReleaseLifecycleStopError as exc:
            return WeeklyLifecycleCronResult(exit_code=1, status="FAILED", message=str(exc), runs=0)

        print(f"Owner lookup OK: {PRODUCTION_OWNER_EMAIL} -> owner_id={owner_id}", flush=True)
        plan = build_weekly_lifecycle_plan()
        print_weekly_plan(anchor=plan.anchor_release_date, run_date=plan.run_date)

        if dry_run:
            return WeeklyLifecycleCronResult(
                exit_code=0,
                status="DRY_RUN",
                message="Configuration OK; dry run skipped capture.",
                runs=0,
                plan_printed=True,
            )

        try:
            runs = run_weekly_lifecycle_batch(
                session,
                database_url=db,
                owner_email=PRODUCTION_OWNER_EMAIL,
                plan=plan,
                runner=runner,
            )
        except ReleaseLifecycleStopError as exc:
            return WeeklyLifecycleCronResult(exit_code=1, status="STOPPED", message=str(exc), runs=0)

        report: P86ReleaseLifecycleReport | None = None
        if runs:
            report = finalize_weekly_lifecycle_report(session, owner_id=owner_id, plan=plan, runs=runs)

        if not runs:
            msg = "Weekly batch produced no new runs (duplicate active job or already running)."
            print(msg, flush=True)
            return WeeklyLifecycleCronResult(exit_code=0, status="SKIPPED", message=msg, runs=0)

        print("--- Weekly lifecycle final summary ---", flush=True)
        print(f"Runs completed: {len(runs)}", flush=True)
        for row in runs:
            print(
                f"  {row.target_release_date} {row.lifecycle_stage} status={row.status} "
                f"issues={row.issue_count} variants={row.variant_count}",
                flush=True,
            )
        if report is not None:
            print(f"Report id: {report.id} overall={report.overall_status}", flush=True)
            print(f"Title: {report.title}", flush=True)
        print("--- end weekly summary ---", flush=True)

        return WeeklyLifecycleCronResult(
            exit_code=0,
            status="OK",
            message="Weekly lifecycle batch finished.",
            runs=len(runs),
            report_id=int(report.id or 0) if report else None,
        )
