"""P86 LoCG release lifecycle capture orchestration."""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlmodel import Session, select

from app.models import User
from app.models.p86_release_lifecycle import (
    P86ReleaseLifecycleRun,
    RUN_STATUS_BLOCKED,
    RUN_STATUS_COMPLETE,
    RUN_STATUS_COMPLETE_WITH_WARNINGS,
    RUN_STATUS_FAILED,
    RUN_STATUS_PENDING,
    RUN_STATUS_RUNNING,
    RUN_STATUS_SKIPPED,
)
from app.services.release_lifecycle_plan import (
    PRODUCTION_OWNER_EMAIL,
    LifecyclePlanItem,
    WeeklyLifecyclePlan,
    build_weekly_lifecycle_plan,
    sequential_execution_order,
)

logger = logging.getLogger(__name__)

API_ROOT = Path(__file__).resolve().parents[2]
CAPTURE_SCRIPT = API_ROOT / "scripts" / "capture_locg_date_details_browser.py"

_SUMMARY_LINE = re.compile(r"^([A-Za-z ]+): (.*)$")


@dataclass
class CaptureProcessResult:
    exit_code: int
    stdout: str
    stderr: str
    parsed: dict[str, str]


class ReleaseLifecycleStopError(Exception):
    """Fatal condition that should abort the full weekly batch."""


def verify_owner_lookup(session: Session, *, email: str = PRODUCTION_OWNER_EMAIL) -> int:
    normalized = email.strip()
    row = session.exec(select(User).where(User.email == normalized)).one_or_none()
    if row is None or row.id is None:
        raise ReleaseLifecycleStopError(f"owner lookup failed for email={normalized!r}")
    return int(row.id)


def verify_database_available(session: Session) -> None:
    session.exec(text("SELECT 1")).one()


def build_capture_argv(*, capture_date: date, email: str = PRODUCTION_OWNER_EMAIL) -> list[str]:
    return [
        sys.executable,
        str(CAPTURE_SCRIPT),
        "--production",
        "--email",
        email,
        "--date",
        capture_date.isoformat(),
        "--headful",
        "--save-raw",
        "--adaptive-delay",
        "--skip-crosswalk",
    ]


def build_capture_command_string(argv: list[str]) -> str:
    return " ".join(argv)


def parse_capture_summary(stdout: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    in_block = False
    for line in stdout.splitlines():
        if line.strip() == "--- LoCG capture final summary ---":
            in_block = True
            continue
        if line.strip() == "--- end final summary ---":
            break
        if not in_block:
            continue
        match = _SUMMARY_LINE.match(line.strip())
        if match:
            parsed[match.group(1).strip()] = match.group(2).strip()
    return parsed


def map_capture_status(*, parsed_status: str, exit_code: int, stderr: str) -> str:
    normalized = parsed_status.upper().replace(" ", "_")
    if normalized == "BLOCKED":
        return RUN_STATUS_BLOCKED
    if normalized in {"COMPLETE", "COMPLETE_WITH_WARNINGS", "DRY_RUN"}:
        if normalized == "COMPLETE_WITH_WARNINGS":
            return RUN_STATUS_COMPLETE_WITH_WARNINGS
        return RUN_STATUS_COMPLETE
    if exit_code == 0 and normalized in {"", "COMPLETE"}:
        return RUN_STATUS_COMPLETE
    lowered = f"{stderr}\n{parsed_status}".lower()
    if "cloudflare" in lowered and "block" in lowered:
        return RUN_STATUS_BLOCKED
    return RUN_STATUS_FAILED


def is_playwright_launch_failure(*, stderr: str, stdout: str) -> bool:
    blob = f"{stderr}\n{stdout}".lower()
    if "playwright" not in blob:
        return False
    return any(token in blob for token in ("launch", "executable", "browser type", "chromium"))


def print_lifecycle_run_summary(
    *,
    capture_date: date,
    lifecycle_stage: str,
    run_status: str,
    parent_queue: int | None,
    parent_captured: int | None,
    issue_count: int | None,
    variant_count: int | None,
    skipped_missing_parent: int | None,
    variant_upsert_failures: int | None,
    warnings: list[str],
    failures: list[str],
    elapsed_seconds: float | None,
    crosswalk_skipped: bool,
    raw_path: str,
) -> None:
    lines = [
        "--- P86 release lifecycle capture summary ---",
        f"Date: {capture_date.isoformat()}",
        f"Lifecycle stage: {lifecycle_stage}",
        f"Run status: {run_status}",
        f"Parent queue: {parent_queue}",
        f"Parent captured: {parent_captured}",
        f"DB issues: {issue_count}",
        f"DB variants: {variant_count}",
        f"Skipped missing parent: {skipped_missing_parent}",
        f"Variant upsert failures: {variant_upsert_failures}",
        f"Warnings: {warnings if warnings else '[]'}",
        f"Failures: {failures if failures else '[]'}",
        f"Elapsed seconds: {elapsed_seconds}",
        f"Crosswalk skipped: {crosswalk_skipped}",
        f"Raw path: {raw_path}",
        "--- end lifecycle summary ---",
    ]
    print("\n".join(lines), flush=True)


def _int_or_none(value: str | None) -> int | None:
    if value is None or value in {"", "None"}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _float_or_none(value: str | None) -> float | None:
    if value is None or value in {"", "None"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_list_field(value: str | None) -> list[str]:
    if not value or value == "[]":
        return []
    try:
        loaded = ast.literal_eval(value)
        if isinstance(loaded, list):
            return [str(x) for x in loaded]
    except (SyntaxError, ValueError):
        pass
    if value.startswith("[") and value.endswith("]"):
        try:
            loaded = json.loads(value.replace("'", '"'))
            if isinstance(loaded, list):
                return [str(x) for x in loaded]
        except json.JSONDecodeError:
            pass
    return [value]


def apply_parsed_summary_to_run(row: P86ReleaseLifecycleRun, parsed: dict[str, str], *, stderr: str, exit_code: int) -> None:
    run_status_raw = parsed.get("Run status", "")
    row.status = map_capture_status(parsed_status=run_status_raw, exit_code=exit_code, stderr=stderr)
    row.parent_queue_count = _int_or_none(parsed.get("Parent queue"))
    row.parent_captured_count = _int_or_none(parsed.get("Parent captured"))
    row.issue_count = _int_or_none(parsed.get("DB issues"))
    row.variant_count = _int_or_none(parsed.get("DB variants"))
    row.elapsed_seconds = _float_or_none(parsed.get("Elapsed seconds"))
    row.raw_path = parsed.get("Raw path") or row.raw_path
    crosswalk = parsed.get("Crosswalk skipped", "True")
    row.crosswalk_skipped = crosswalk.lower() in {"true", "1", "yes"}
    row.warnings_json = _parse_list_field(parsed.get("Warnings"))
    row.failures_json = _parse_list_field(parsed.get("Failures"))
    if stderr.strip() and not row.failures_json:
        row.failures_json = [stderr.strip()[:2000]]


def has_active_lifecycle_runs(session: Session, *, owner_id: int) -> bool:
    active = session.exec(
        select(P86ReleaseLifecycleRun)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .where(P86ReleaseLifecycleRun.status == RUN_STATUS_RUNNING)
    ).first()
    return active is not None


def weekly_batch_exists(
    session: Session,
    *,
    owner_id: int,
    anchor_release_date: date,
    run_date: date,
) -> bool:
    row = session.exec(
        select(P86ReleaseLifecycleRun)
        .where(P86ReleaseLifecycleRun.owner_id == owner_id)
        .where(P86ReleaseLifecycleRun.anchor_release_date == anchor_release_date)
        .where(P86ReleaseLifecycleRun.run_date == run_date)
        .where(P86ReleaseLifecycleRun.status.in_([RUN_STATUS_RUNNING, RUN_STATUS_PENDING]))
    ).first()
    return row is not None


def run_capture_subprocess(
    *,
    argv: list[str],
    database_url: str,
    cwd: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> CaptureProcessResult:
    if not database_url.strip():
        raise ReleaseLifecycleStopError("DATABASE_URL is required for lifecycle capture")
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url.strip()
    invoke = runner or subprocess.run
    completed = invoke(
        argv,
        cwd=str(cwd or API_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    parsed = parse_capture_summary(stdout)
    return CaptureProcessResult(exit_code=int(completed.returncode), stdout=stdout, stderr=stderr, parsed=parsed)


def run_single_lifecycle_capture(
    session: Session,
    *,
    owner_id: int,
    plan: WeeklyLifecyclePlan,
    item: LifecyclePlanItem,
    database_url: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    existing_run_id: int | None = None,
) -> P86ReleaseLifecycleRun:
    argv = build_capture_argv(capture_date=item.target_release_date)
    command = build_capture_command_string(argv)
    now = datetime.now(timezone.utc)

    if existing_run_id is not None:
        row = session.get(P86ReleaseLifecycleRun, existing_run_id)
        if row is None:
            raise ValueError(f"lifecycle run {existing_run_id} not found")
    else:
        row = P86ReleaseLifecycleRun(
            owner_id=owner_id,
            run_date=plan.run_date,
            anchor_release_date=plan.anchor_release_date,
            target_release_date=item.target_release_date,
            lifecycle_stage=item.lifecycle_stage,
            command=command,
            status=RUN_STATUS_PENDING,
            crosswalk_skipped=True,
        )
        session.add(row)
        session.commit()
        session.refresh(row)

    assert row.id is not None
    row.status = RUN_STATUS_RUNNING
    row.started_at = now
    row.command = command
    row.updated_at = now
    session.add(row)
    session.commit()

    started = time.perf_counter()
    try:
        result = run_capture_subprocess(argv=argv, database_url=database_url, runner=runner)
    except ReleaseLifecycleStopError:
        raise
    except Exception as exc:  # noqa: BLE001
        row.status = RUN_STATUS_FAILED
        row.failures_json = [str(exc)]
        row.completed_at = datetime.now(timezone.utc)
        row.elapsed_seconds = round(time.perf_counter() - started, 1)
        row.updated_at = row.completed_at
        session.add(row)
        session.commit()
        session.refresh(row)
        if is_playwright_launch_failure(stderr=str(exc), stdout=""):
            raise ReleaseLifecycleStopError(str(exc)) from exc
        return row

    apply_parsed_summary_to_run(row, result.parsed, stderr=result.stderr, exit_code=result.exit_code)
    if row.status == RUN_STATUS_FAILED and is_playwright_launch_failure(stderr=result.stderr, stdout=result.stdout):
        row.completed_at = datetime.now(timezone.utc)
        row.elapsed_seconds = round(time.perf_counter() - started, 1)
        row.updated_at = row.completed_at
        session.add(row)
        session.commit()
        session.refresh(row)
        raise ReleaseLifecycleStopError(result.stderr or "Playwright failed to launch")

    row.completed_at = datetime.now(timezone.utc)
    if row.elapsed_seconds is None:
        row.elapsed_seconds = round(time.perf_counter() - started, 1)
    row.updated_at = row.completed_at
    session.add(row)
    session.commit()
    session.refresh(row)

    print_lifecycle_run_summary(
        capture_date=item.target_release_date,
        lifecycle_stage=item.lifecycle_stage,
        run_status=row.status,
        parent_queue=row.parent_queue_count,
        parent_captured=row.parent_captured_count,
        issue_count=row.issue_count,
        variant_count=row.variant_count,
        skipped_missing_parent=_int_or_none(result.parsed.get("Skipped missing parent")),
        variant_upsert_failures=_int_or_none(result.parsed.get("Variant upsert failures")),
        warnings=list(row.warnings_json or []),
        failures=list(row.failures_json or []),
        elapsed_seconds=row.elapsed_seconds,
        crosswalk_skipped=row.crosswalk_skipped,
        raw_path=row.raw_path,
    )
    return row


def run_weekly_lifecycle_batch(
    session: Session,
    *,
    database_url: str,
    owner_email: str = PRODUCTION_OWNER_EMAIL,
    plan: WeeklyLifecyclePlan | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    skip_post_refresh: bool = False,
) -> list[P86ReleaseLifecycleRun]:
    owner_id = verify_owner_lookup(session, email=owner_email)
    verify_database_available(session)
    batch_plan = plan or build_weekly_lifecycle_plan()

    if has_active_lifecycle_runs(session, owner_id=owner_id):
        logger.warning("Skipping weekly lifecycle: capture already RUNNING for owner_id=%s", owner_id)
        return []

    if weekly_batch_exists(
        session,
        owner_id=owner_id,
        anchor_release_date=batch_plan.anchor_release_date,
        run_date=batch_plan.run_date,
    ):
        logger.info("Skipping weekly lifecycle: batch already active for anchor=%s", batch_plan.anchor_release_date)
        return []

    ordered = sequential_execution_order(list(batch_plan.items))
    results: list[P86ReleaseLifecycleRun] = []
    consecutive_blocked = 0

    for item in ordered:
        if "--skip-crosswalk" not in build_capture_argv(capture_date=item.target_release_date):
            raise ReleaseLifecycleStopError("capture command must include --skip-crosswalk")

        row = run_single_lifecycle_capture(
            session,
            owner_id=owner_id,
            plan=batch_plan,
            item=item,
            database_url=database_url,
            runner=runner,
        )
        results.append(row)

        if row.status == RUN_STATUS_BLOCKED:
            consecutive_blocked += 1
            if consecutive_blocked >= 2:
                logger.error("Stopping weekly lifecycle after consecutive Cloudflare blocks")
                break
        else:
            consecutive_blocked = 0

    if results and not skip_post_refresh:
        run_post_weekly_refreshes(session, owner_user_id=owner_id)

    return results


def run_post_weekly_refreshes(session: Session, *, owner_user_id: int) -> None:
    from app.services.foc_purchase_intelligence_service import build_foc_dashboard
    from app.services.p81_discovery_personalization_service import refresh_personalized_discovery
    from app.services.p81_discovery_service import refresh_discovery
    from app.services.release_monitoring_service import build_release_monitoring_dashboard

    try:
        refresh_discovery(session, owner_user_id=owner_user_id)
        refresh_personalized_discovery(session, owner_user_id=owner_user_id, ingest=True)
        build_release_monitoring_dashboard(session, owner_user_id=owner_user_id, persist=True)
        build_foc_dashboard(session, owner_user_id=owner_user_id)
        from app.services.cross_system_recommendation import generate_cross_system_recommendations

        generate_cross_system_recommendations(session, owner_user_id=owner_user_id, refresh_upstream=False)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Post-weekly lifecycle refresh partial failure: %s", exc)


def retry_lifecycle_run(
    session: Session,
    *,
    run_id: int,
    owner_id: int,
    database_url: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> P86ReleaseLifecycleRun:
    row = session.get(P86ReleaseLifecycleRun, run_id)
    if row is None or row.owner_id != owner_id:
        raise LookupError("lifecycle run not found")
    if row.status not in {RUN_STATUS_BLOCKED, RUN_STATUS_FAILED}:
        raise ValueError("only BLOCKED or FAILED runs can be retried")
    plan = WeeklyLifecyclePlan(
        anchor_release_date=row.anchor_release_date,
        run_date=row.run_date,
        items=(
            LifecyclePlanItem(
                target_release_date=row.target_release_date,
                lifecycle_stage=row.lifecycle_stage,
            ),
        ),
    )
    item = plan.items[0]
    row.status = RUN_STATUS_PENDING
    row.failures_json = []
    row.warnings_json = []
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    return run_single_lifecycle_capture(
        session,
        owner_id=owner_id,
        plan=plan,
        item=item,
        database_url=database_url,
        runner=runner,
        existing_run_id=int(row.id or 0),
    )
