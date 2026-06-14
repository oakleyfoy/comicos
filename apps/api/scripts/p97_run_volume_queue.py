"""P97 exact-volume queue runner — safe, single-worker, rate-budgeted acquisition.

This runner imports exact ComicVine volume ids from ``p97_comicvine_volume_queue``.
It NEVER performs publisher offset crawling or series search crawling. It checks the
ComicVine request budget (backed by ``p97_comicvine_request_ledger``) BEFORE every API
call, pauses the whole queue for 4 hours on any HTTP 420 (no immediate retry), and never
re-imports a row already marked ``imported`` unless ``--reprocess`` is given.

Usage:
  python scripts/p97_run_volume_queue.py
  python scripts/p97_run_volume_queue.py --limit 10
  python scripts/p97_run_volume_queue.py --watch
  python scripts/p97_run_volume_queue.py --max-requests-per-hour 120
  python scripts/p97_run_volume_queue.py --min-seconds-between-requests 30
  python scripts/p97_run_volume_queue.py --pause-hours-on-420 4
  python scripts/p97_run_volume_queue.py --dry-run
  python scripts/p97_run_volume_queue.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.comicvine_catalog_importer import ComicVineCatalogImporter  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p97_volume_queue_service import (  # noqa: E402
    STATUS_IMPORTED,
    apply_import_result,
    issues_per_api_request,
    mark_importing,
    queue_counts,
    reset_throttled_to_pending,
    select_next_pending,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DATA_DIR = API_ROOT / "data" / "p97"
LOCK_FILE = DATA_DIR / "volume_queue_runner.lock"
PROGRESS_FILE = DATA_DIR / "volume_queue_progress.json"

GOAL_PRIMARY = 150000
GOAL_STRETCH = 200000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --- single-worker lock ---------------------------------------------------

def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_lock_pid(lock_path: Path) -> int | None:
    if not lock_path.is_file():
        return None
    try:
        return int((lock_path.read_text(encoding="utf-8").strip() or "0"))
    except (OSError, ValueError):
        return None


def acquire_runner_lock(lock_path: Path = LOCK_FILE) -> bool:
    """Acquire the single-worker lock. Returns False if a live runner already holds it."""
    existing_pid = read_lock_pid(lock_path)
    if existing_pid is not None and existing_pid != os.getpid() and _pid_alive(existing_pid):
        return False
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_runner_lock(lock_path: Path = LOCK_FILE) -> None:
    pid = read_lock_pid(lock_path)
    if pid is None or pid == os.getpid():
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


# --- command composition (exact volume only) ------------------------------

def build_volume_import_command(volume_id: int, *, import_issues: bool = True) -> list[str]:
    """Compose the equivalent exact-volume import command (logging / verification).

    Never includes --publisher, --series-name, --offset, or --strict-publisher.
    """
    cmd = [
        "python",
        "scripts/p97_import_comicvine_catalog.py",
        "--volume-id",
        str(int(volume_id)),
    ]
    if import_issues:
        cmd.append("--import-issues")
    return cmd


# --- ledger recording -----------------------------------------------------

def record_requests_for_import(
    budget: ComicVineRateBudget,
    *,
    volume_id: int,
    queue_id: int | None,
    api_requests_used: int,
    throttled: bool,
) -> None:
    n = max(0, int(api_requests_used))
    if throttled:
        for _ in range(max(0, n - 1)):
            budget.record_request(
                request_type="issue_import",
                comicvine_volume_id=volume_id,
                queue_id=queue_id,
                status_code=200,
            )
        budget.record_420(comicvine_volume_id=volume_id, queue_id=queue_id)
        return
    for _ in range(n):
        budget.record_request(
            request_type="issue_import",
            comicvine_volume_id=volume_id,
            queue_id=queue_id,
            status_code=200,
        )


# --- progress artifact ----------------------------------------------------

def _catalog_issue_count(session: Session) -> int:
    from sqlalchemy import func
    from sqlmodel import select

    from app.models.catalog_master import CatalogIssue

    return int(session.exec(select(func.count()).select_from(CatalogIssue)).one())


def build_progress_document(
    session: Session,
    budget: ComicVineRateBudget,
    *,
    status: str,
    started_at: datetime,
    current_volume_id: int | None,
    current_series_name: str | None,
    current_publisher: str | None,
    issues_created_run: int,
    issues_updated_run: int,
    images_created_run: int,
    api_requests_run: int,
    now: datetime | None = None,
) -> dict:
    now = now or _utc_now()
    counts = queue_counts(session)
    requests_last_hour = budget.get_requests_last_hour(now=now)
    last_420 = budget.get_last_420()
    pause_until = budget.pause_until()
    current_catalog_issues = _catalog_issue_count(session)
    ipar = issues_per_api_request(issues_created_run, api_requests_run)
    eta_days = _eta_days_to_goal(current_catalog_issues, issues_created_run, started_at, now)
    return {
        "mode": "volume_queue",
        "status": status,
        "started_at": started_at.isoformat(),
        "updated_at": now.isoformat(),
        "current_volume_id": current_volume_id,
        "current_series_name": current_series_name,
        "current_publisher": current_publisher,
        "queue_pending": counts.get("pending", 0),
        "queue_imported": counts.get("imported", 0),
        "queue_failed": counts.get("failed", 0),
        "queue_throttled": counts.get("throttled", 0),
        "requests_last_hour": requests_last_hour,
        "max_requests_per_hour": budget.max_requests_per_hour,
        "min_seconds_between_requests": budget.min_seconds_between_requests,
        "last_420_at": last_420.isoformat() if last_420 else None,
        "pause_until": pause_until.isoformat() if pause_until else None,
        "issues_created_run": issues_created_run,
        "issues_updated_run": issues_updated_run,
        "images_created_run": images_created_run,
        "api_requests_run": api_requests_run,
        "issues_per_api_request": ipar,
        "current_catalog_issues": current_catalog_issues,
        "goal_150k_remaining": max(0, GOAL_PRIMARY - current_catalog_issues),
        "goal_200k_remaining": max(0, GOAL_STRETCH - current_catalog_issues),
        "eta_days_to_150k": eta_days,
    }


def _eta_days_to_goal(
    current_catalog_issues: int,
    issues_created_run: int,
    started_at: datetime,
    now: datetime,
) -> float | None:
    remaining = max(0, GOAL_PRIMARY - current_catalog_issues)
    if remaining <= 0:
        return 0.0
    elapsed_seconds = max(1.0, (now - started_at).total_seconds())
    if issues_created_run <= 0:
        return None
    per_day = issues_created_run / (elapsed_seconds / 86400.0)
    if per_day <= 0:
        return None
    return round(remaining / per_day, 1)


def write_progress_artifact(document: dict, path: Path = PROGRESS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")


# --- run loop -------------------------------------------------------------

def run_queue(
    session: Session,
    *,
    max_requests_per_hour: int,
    min_seconds_between_requests: float,
    pause_hours_on_420: float,
    limit: int | None,
    watch: bool,
    dry_run: bool,
    reprocess: bool,
    sleep_fn=time.sleep,
    json_output: bool = False,
) -> dict:
    started_at = _utc_now()
    budget = ComicVineRateBudget(
        session,
        max_requests_per_hour=max_requests_per_hour,
        min_seconds_between_requests=min_seconds_between_requests,
        pause_hours_on_420=pause_hours_on_420,
    )
    importer = None if dry_run else ComicVineCatalogImporter()
    if importer is not None:
        msg = importer.initialize_or_explain()
        if msg:
            return {"status": "error", "error": msg}

    processed = 0
    issues_created_run = 0
    issues_updated_run = 0
    images_created_run = 0
    api_requests_run = 0
    status = "idle"
    current_volume_id: int | None = None
    current_series_name: str | None = None
    current_publisher: str | None = None

    while True:
        # Re-queue throttled rows only once the pause window has elapsed.
        if not budget.should_pause_for_420():
            reset_throttled_to_pending(session)

        if budget.should_pause_for_420():
            status = "paused_420"
            wait = budget.seconds_until_next_request()
            if not watch:
                break
            sleep_fn(min(wait, 300.0) if wait > 0 else 60.0)
            continue

        decision = budget.evaluate()
        if not decision.allowed:
            status = "rate_limited"
            if not watch:
                break
            sleep_fn(min(decision.seconds_until_next_request, 300.0) if decision.seconds_until_next_request > 0 else 30.0)
            continue

        row = select_next_pending(session)
        if row is None:
            status = "queue_empty"
            if not watch:
                break
            sleep_fn(60.0)
            continue

        current_volume_id = row.comicvine_volume_id
        current_series_name = row.series_name
        current_publisher = row.publisher

        if dry_run:
            status = "dry_run"
            plan = {
                "next_volume_id": row.comicvine_volume_id,
                "series_name": row.series_name,
                "publisher": row.publisher,
                "command": build_volume_import_command(row.comicvine_volume_id),
            }
            if json_output:
                print(json.dumps(plan, separators=(",", ":")))
            else:
                print("DRY RUN - next exact volume import:")
                print(f"  volume_id={row.comicvine_volume_id} series={row.series_name!r} publisher={row.publisher!r}")
                print("  " + " ".join(build_volume_import_command(row.comicvine_volume_id)))
            break

        mark_importing(session, row)
        assert importer is not None
        stats = importer.import_single_volume(
            session,
            comicvine_volume_id=row.comicvine_volume_id,
            import_issues=True,
        )
        record_requests_for_import(
            budget,
            volume_id=row.comicvine_volume_id,
            queue_id=row.id,
            api_requests_used=stats.api_requests_used,
            throttled=stats.throttled,
        )
        failed = bool(stats.failures) and not stats.throttled
        apply_import_result(
            session,
            row,
            issues_created=stats.created_issues,
            issues_updated=stats.updated_issues,
            images_created=stats.cover_images_created,
            api_requests_used=stats.api_requests_used,
            throttled=stats.throttled,
            failed=failed,
            last_error=(stats.failures[0] if stats.failures else None),
        )
        processed += 1
        issues_created_run += stats.created_issues
        issues_updated_run += stats.updated_issues
        images_created_run += stats.cover_images_created
        api_requests_run += stats.api_requests_used

        if stats.throttled:
            status = "paused_420"
            document = build_progress_document(
                session, budget, status=status, started_at=started_at,
                current_volume_id=current_volume_id, current_series_name=current_series_name,
                current_publisher=current_publisher, issues_created_run=issues_created_run,
                issues_updated_run=issues_updated_run, images_created_run=images_created_run,
                api_requests_run=api_requests_run,
            )
            write_progress_artifact(document)
            if not watch:
                break
            sleep_fn(min(budget.seconds_until_next_request(), 300.0))
            continue

        status = "running"
        document = build_progress_document(
            session, budget, status=status, started_at=started_at,
            current_volume_id=current_volume_id, current_series_name=current_series_name,
            current_publisher=current_publisher, issues_created_run=issues_created_run,
            issues_updated_run=issues_updated_run, images_created_run=images_created_run,
            api_requests_run=api_requests_run,
        )
        write_progress_artifact(document)

        if limit is not None and processed >= limit:
            status = "limit_reached"
            break

        # Conservative spacing between volume imports.
        wait = budget.seconds_until_next_request()
        if wait > 0:
            sleep_fn(wait)

    document = build_progress_document(
        session, budget, status=status, started_at=started_at,
        current_volume_id=current_volume_id, current_series_name=current_series_name,
        current_publisher=current_publisher, issues_created_run=issues_created_run,
        issues_updated_run=issues_updated_run, images_created_run=images_created_run,
        api_requests_run=api_requests_run,
    )
    if not dry_run:
        write_progress_artifact(document)
    document["processed"] = processed
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 exact-volume queue runner (single worker, rate-budgeted)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--limit", type=int, default=None, help="Max volumes to import this run")
    parser.add_argument("--watch", action="store_true", help="Run continuously, sleeping when blocked/empty")
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    parser.add_argument("--min-seconds-between-requests", type=float, default=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS)
    parser.add_argument("--pause-hours-on-420", type=float, default=DEFAULT_PAUSE_HOURS_ON_420)
    parser.add_argument("--dry-run", action="store_true", help="Show next planned import without any API call")
    parser.add_argument("--reprocess", action="store_true", help="(reserved) allow reprocessing imported rows")
    parser.add_argument("--json", action="store_true", help="Emit final run summary as JSON")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    if not args.dry_run and not acquire_runner_lock():
        pid = read_lock_pid(LOCK_FILE)
        print(f"ERROR: another volume queue runner is active (pid={pid}); refusing to start.", file=sys.stderr)
        return 2
    try:
        with Session(engine) as session:
            result = run_queue(
                session,
                max_requests_per_hour=args.max_requests_per_hour,
                min_seconds_between_requests=args.min_seconds_between_requests,
                pause_hours_on_420=args.pause_hours_on_420,
                limit=args.limit,
                watch=args.watch,
                dry_run=args.dry_run,
                reprocess=args.reprocess,
                json_output=args.json,
            )
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    finally:
        if not args.dry_run:
            release_runner_lock()

    if result.get("status") == "error":
        print(f"ERROR: {result.get('error')}", file=sys.stderr)
        return 1
    if args.json and not args.dry_run:
        print(json.dumps(result, separators=(",", ":")))
    elif not args.dry_run:
        print(
            f"status={result.get('status')} processed={result.get('processed', 0)} "
            f"issues_created_run={result.get('issues_created_run', 0)} "
            f"api_requests_run={result.get('api_requests_run', 0)} "
            f"queue_pending={result.get('queue_pending', 0)} "
            f"queue_imported={result.get('queue_imported', 0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
