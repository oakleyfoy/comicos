"""P99-03 — Execute a pending queue drain batch (dry-run default)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.comicvine_catalog_importer import ComicVineCatalogImporter  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p99_pending_queue_batch_executor_service import (  # noqa: E402
    assert_apply_allowed,
    build_batch_volume_plan,
    default_core_drain_progress_path,
    default_progress_path,
    execute_pending_queue_batch,
    save_batch_progress,
    save_core_queue_drain_progress,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P99 pending queue batch executor")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--batch", type=str, default="1", help="1, 2, 3, group1, or group2")
    parser.add_argument("--apply", action="store_true", help="Run imports (default: dry-run)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit-issues", type=int, default=None)
    parser.add_argument("--inter-volume-delay", type=float, default=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS)
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    parser.add_argument(
        "--min-seconds-between-requests",
        type=float,
        default=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    )
    parser.add_argument("--pause-hours-on-420", type=float, default=DEFAULT_PAUSE_HOURS_ON_420)
    parser.add_argument("--max-volumes", type=int, default=None, help="Cap volumes processed this run")
    parser.add_argument("--http-timeout", type=float, default=30.0)
    args = parser.parse_args()

    dry_run = not args.apply
    try:
        assert_apply_allowed(args.batch, apply=not dry_run)
    except ValueError as exc:
        _log(str(exc))
        return 2

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    with Session(engine) as session:
        plan = build_batch_volume_plan(session, args.batch, max_volumes=args.max_volumes)
        budget = ComicVineRateBudget(
            session,
            max_requests_per_hour=args.max_requests_per_hour,
            min_seconds_between_requests=args.min_seconds_between_requests,
            pause_hours_on_420=args.pause_hours_on_420,
        )
        importer = ComicVineCatalogImporter(dry_run=dry_run, http_timeout=float(args.http_timeout))
        if not dry_run:
            missing = importer.initialize_or_explain()
            if missing:
                _log(missing)
                return 1

        result = execute_pending_queue_batch(
            session,
            budget,
            importer,
            plan,
            dry_run=dry_run,
            inter_volume_delay_seconds=float(args.inter_volume_delay),
            issues_limit=args.limit_issues,
            verbose=not args.json,
        )

    save_batch_progress(result)
    save_core_queue_drain_progress(result, max_volumes=args.max_volumes)

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
        return 0

    mode = "DRY RUN" if dry_run else "APPLY"
    first = plan.first_volume or {}
    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Mode: {mode}")
    _log(f"Batch: {plan.batch_key} ({plan.batch_id})")
    _log(f"Progress file: {default_progress_path()}")
    if plan.batch_key == "group1":
        _log(f"Core drain progress: {default_core_drain_progress_path()}")
    _log("")
    _log(f"Volumes Selected: {plan.volumes_selected}")
    _log(f"Estimated Shell Gap: {plan.estimated_shell_gap}")
    _log(f"Estimated Catalog Gain: {plan.estimated_catalog_gain}")
    if first:
        _log(
            f"First Volume:\n{first.get('volume')} / {first.get('publisher')}"
        )
    _log("")
    if dry_run:
        _log(f"Would process (pending verified): {result.volumes_processed}")
        _log(f"Skipped: {result.volumes_skipped}")
        if result.group1_volumes_remaining is not None:
            _log(f"GROUP_1 pending volumes (total): {result.group1_volumes_remaining}")
    else:
        _log(f"Processed: {result.volumes_processed}")
        _log(f"Completed: {result.volumes_completed}")
        _log(f"Failed: {result.volumes_failed}")
        _log(f"Skipped: {result.volumes_skipped}")
        if result.group1_volumes_remaining is not None:
            _log(f"GROUP_1 volumes remaining: {result.group1_volumes_remaining}")
        if result.group1_pending_shell_reduction is not None:
            _log(f"GROUP_1 pending shell reduction: {result.group1_pending_shell_reduction}")
    for skip in result.skipped_rows:
        _log(f"  SKIP cv={skip.comicvine_volume_id} {skip.volume[:40]} reason={skip.reason}")
    if not dry_run:
        _log(f"Catalog before: {result.catalog_count_before:,}")
        _log(f"Catalog after:  {result.catalog_count_after:,}")
        _log(f"Catalog gain:   {result.catalog_gain:,}")
        _log("")
        _log("Post-run validation:")
        _log("  python scripts/p99_catalog_acquisition_gap_report.py")
        _log("  python scripts/p98_major_publisher_completeness_report.py")
    else:
        _log("")
        _log("Dry-run only — pass --apply for batch 1 or group1 imports.")
    if result.stopped_reason:
        _log(f"Stopped: {result.stopped_reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
