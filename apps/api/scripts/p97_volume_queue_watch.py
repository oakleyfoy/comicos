"""P97 known-good volume queue watcher (read-only).

Displays queue counts, ComicVine request budget, last 420 / pause window, issues created,
issues-per-API-request, and ETA to 150k. Reads live DB state plus the optional run artifact
``data/p97/volume_queue_progress.json``.

Usage:
  python scripts/p97_volume_queue_watch.py
  python scripts/p97_volume_queue_watch.py --watch 30
  python scripts/p97_volume_queue_watch.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlalchemy import func  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.models.catalog_master import CatalogIssue  # noqa: E402
from app.models.catalog_p97 import P97ComicVineVolumeQueue  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    ComicVineRateBudget,
)
from app.services.p97_volume_queue_service import (  # noqa: E402
    STATUS_IMPORTED,
    issues_per_api_request,
    queue_counts,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

PROGRESS_FILE = API_ROOT / "data" / "p97" / "volume_queue_progress.json"
GOAL_PRIMARY = 150000
GOAL_STRETCH = 200000


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _load_progress(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None


def collect_watch_report(
    session: Session,
    *,
    max_requests_per_hour: int = DEFAULT_MAX_REQUESTS_PER_HOUR,
    progress: dict | None = None,
    now: datetime | None = None,
) -> dict:
    now = now or _utc_now()
    budget = ComicVineRateBudget(session, max_requests_per_hour=max_requests_per_hour)
    counts = queue_counts(session)
    requests_last_hour = budget.get_requests_last_hour(now=now)
    last_420 = budget.get_last_420()
    pause_until = budget.pause_until()

    today_start = _today_start(now)
    created_today = int(
        session.exec(
            select(func.coalesce(func.sum(P97ComicVineVolumeQueue.issues_created), 0)).where(
                P97ComicVineVolumeQueue.last_imported_at >= today_start
            )
        ).one()
    )
    updated_today = int(
        session.exec(
            select(func.coalesce(func.sum(P97ComicVineVolumeQueue.issues_updated), 0)).where(
                P97ComicVineVolumeQueue.last_imported_at >= today_start
            )
        ).one()
    )

    last_imported = session.exec(
        select(P97ComicVineVolumeQueue)
        .where(P97ComicVineVolumeQueue.status == STATUS_IMPORTED)
        .where(P97ComicVineVolumeQueue.last_imported_at.is_not(None))
        .order_by(P97ComicVineVolumeQueue.last_imported_at.desc())
    ).first()

    current_catalog_issues = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())

    progress = progress or {}
    issues_created_run = int(progress.get("issues_created_run", 0) or 0)
    api_requests_run = int(progress.get("api_requests_run", 0) or 0)
    ipar_run = issues_per_api_request(issues_created_run, api_requests_run)

    return {
        "status": progress.get("status", "unknown"),
        "queue_pending": counts.get("pending", 0),
        "queue_imported": counts.get("imported", 0),
        "queue_failed": counts.get("failed", 0),
        "queue_throttled": counts.get("throttled", 0),
        "requests_last_hour": requests_last_hour,
        "max_requests_per_hour": max_requests_per_hour,
        "request_budget_remaining": max(0, max_requests_per_hour - requests_last_hour),
        "last_420_at": last_420.isoformat() if last_420 else None,
        "pause_until": pause_until.isoformat() if pause_until else None,
        "issues_created_today": created_today,
        "issues_updated_today": updated_today,
        "issues_created_run": issues_created_run,
        "issues_per_api_request": ipar_run,
        "current_catalog_issues": current_catalog_issues,
        "remaining_to_150k": max(0, GOAL_PRIMARY - current_catalog_issues),
        "remaining_to_200k": max(0, GOAL_STRETCH - current_catalog_issues),
        "eta_days_to_150k": progress.get("eta_days_to_150k"),
        "last_imported_volume_id": last_imported.comicvine_volume_id if last_imported else None,
        "last_imported_series": last_imported.series_name if last_imported else None,
        "report_at": now.isoformat(),
    }


def _fmt(value) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.3f}"
    return str(value)


def format_table(report: dict) -> str:
    lines = [
        "P97 Known Good Volume Queue",
        "=" * 52,
        f"{'Status':<26}{report.get('status', '—')}",
        "",
        "Queue",
        "-" * 52,
        f"{'Pending':<26}{_fmt(report['queue_pending'])}",
        f"{'Imported':<26}{_fmt(report['queue_imported'])}",
        f"{'Failed':<26}{_fmt(report['queue_failed'])}",
        f"{'Throttled':<26}{_fmt(report['queue_throttled'])}",
        "",
        "ComicVine Budget",
        "-" * 52,
        f"{'Requests last hour':<26}{_fmt(report['requests_last_hour'])} / {_fmt(report['max_requests_per_hour'])}",
        f"{'Budget remaining':<26}{_fmt(report['request_budget_remaining'])}",
        f"{'Last 420 at':<26}{report.get('last_420_at') or '—'}",
        f"{'Pause until':<26}{report.get('pause_until') or '—'}",
        "",
        "Throughput",
        "-" * 52,
        f"{'Issues created today':<26}{_fmt(report['issues_created_today'])}",
        f"{'Issues updated today':<26}{_fmt(report['issues_updated_today'])}",
        f"{'Issues created (run)':<26}{_fmt(report['issues_created_run'])}",
        f"{'Issues / API request':<26}{_fmt(report['issues_per_api_request'])}",
        f"{'ETA days to 150k':<26}{_fmt(report.get('eta_days_to_150k'))}",
        "",
        "Catalog",
        "-" * 52,
        f"{'Current catalog issues':<26}{_fmt(report['current_catalog_issues'])}",
        f"{'Remaining to 150k':<26}{_fmt(report['remaining_to_150k'])}",
        f"{'Remaining to 200k':<26}{_fmt(report['remaining_to_200k'])}",
        f"{'Last imported volume':<26}{_fmt(report.get('last_imported_volume_id'))}",
        f"{'Last imported series':<26}{report.get('last_imported_series') or '—'}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 volume queue watcher (read-only)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="Refresh every N seconds until Ctrl+C")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    def render_once() -> int:
        try:
            with Session(engine) as session:
                report = collect_watch_report(
                    session,
                    max_requests_per_hour=args.max_requests_per_hour,
                    progress=_load_progress(PROGRESS_FILE),
                )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: database connection failed: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(report, separators=(",", ":")))
        else:
            print(format_table(report))
        return 0

    if args.watch is not None:
        if args.watch <= 0:
            print("ERROR: --watch must be a positive integer.", file=sys.stderr)
            return 1
        try:
            while True:
                print(f"\n--- {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC ---")
                code = render_once()
                if code != 0:
                    return code
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

    return render_once()


if __name__ == "__main__":
    raise SystemExit(main())
