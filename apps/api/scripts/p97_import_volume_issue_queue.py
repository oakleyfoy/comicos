"""Import ComicVine issues for pending P97 volume issue import queue rows.

Usage:
  python scripts/p97_import_volume_issue_queue.py --tier tier_1_core --limit-volumes 10
  python scripts/p97_import_volume_issue_queue.py --limit-volumes 5 --dry-run
  python scripts/p97_import_volume_issue_queue.py --tier tier_1_core --limit-issues 50 --max-api-requests 20
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.comicvine_catalog_importer import ComicVineCatalogImporter  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p97_volume_issue_queue_import_service import (  # noqa: E402
    run_volume_issue_queue_import,
)
from app.services.p97_volume_issue_queue_priority import LAUNCH_PRIORITY_TIERS  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _print_item(item) -> None:
    print(
        f"volume_id={item.volume_id} tier={item.launch_priority_tier} "
        f"name={item.name!r} created={item.created_issues} updated={item.updated_issues} "
        f"api_requests={item.api_requests_used} status={item.queue_status or 'dry_run'}"
    )
    if item.failures:
        print(f"  failures: {'; '.join(item.failures[:3])}")


def _print_summary(result) -> None:
    print("")
    print("P97 VOLUME ISSUE QUEUE IMPORT SUMMARY")
    print(f"  dry_run={result.dry_run} tier_filter={result.tier_filter!r}")
    print(f"  selected={result.volumes_selected} processed={result.volumes_processed}")
    print(f"  complete={result.volumes_complete} failed={result.volumes_failed} pending={result.volumes_pending}")
    print(
        f"  created_issues={result.total_created_issues} "
        f"updated_issues={result.total_updated_issues} api_requests={result.total_api_requests}"
    )
    if result.stopped_reason:
        print(f"  stopped_reason={result.stopped_reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import ComicVine issues from P97 volume issue import queue")
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--tier",
        default=None,
        choices=LAUNCH_PRIORITY_TIERS,
        help="Only import pending rows in this launch tier (required for tier_0/tier_4)",
    )
    parser.add_argument("--limit-volumes", type=int, default=10)
    parser.add_argument("--limit-issues", type=int, default=None, help="Issues per volume API chunk (default 100)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--stop-on-throttle",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stop the run after throttle/connection reset (default: true)",
    )
    parser.add_argument("--max-api-requests", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    parser.add_argument(
        "--min-seconds-between-requests",
        type=float,
        default=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    )
    parser.add_argument("--pause-hours-on-420", type=float, default=DEFAULT_PAUSE_HOURS_ON_420)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    with Session(engine) as session:
        budget = ComicVineRateBudget(
            session,
            max_requests_per_hour=args.max_requests_per_hour,
            min_seconds_between_requests=args.min_seconds_between_requests,
            pause_hours_on_420=args.pause_hours_on_420,
        )
        importer = ComicVineCatalogImporter(dry_run=bool(args.dry_run))
        if not args.dry_run:
            missing = importer.initialize_or_explain()
            if missing:
                print(missing, file=sys.stderr)
                return 1

        result = run_volume_issue_queue_import(
            session,
            budget,
            importer,
            tier=args.tier,
            limit_volumes=args.limit_volumes,
            issues_limit=args.limit_issues,
            dry_run=bool(args.dry_run),
            stop_on_throttle=bool(args.stop_on_throttle),
            max_api_requests=args.max_api_requests,
        )

    if args.json:
        print(
            json.dumps(
                {
                    "dry_run": result.dry_run,
                    "tier_filter": result.tier_filter,
                    "volumes_selected": result.volumes_selected,
                    "volumes_processed": result.volumes_processed,
                    "volumes_complete": result.volumes_complete,
                    "volumes_failed": result.volumes_failed,
                    "volumes_pending": result.volumes_pending,
                    "total_created_issues": result.total_created_issues,
                    "total_updated_issues": result.total_updated_issues,
                    "total_api_requests": result.total_api_requests,
                    "stopped_reason": result.stopped_reason,
                    "items": [
                        {
                            "volume_id": item.volume_id,
                            "name": item.name,
                            "launch_priority_tier": item.launch_priority_tier,
                            "created_issues": item.created_issues,
                            "updated_issues": item.updated_issues,
                            "api_requests_used": item.api_requests_used,
                            "queue_status": item.queue_status,
                            "throttled": item.throttled,
                            "failures": item.failures,
                        }
                        for item in result.items
                    ],
                },
                indent=2,
            )
        )
    else:
        for item in result.items:
            _print_item(item)
        _print_summary(result)

    if result.stopped_reason in ("throttle", "connection_reset"):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
