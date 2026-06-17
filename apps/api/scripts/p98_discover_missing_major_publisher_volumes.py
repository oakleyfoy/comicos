"""P98 — Discover ComicVine volumes missing from the master universe (dry-run default).

Examples:
  python scripts/p98_discover_missing_major_publisher_volumes.py --publisher Marvel --limit-pages 5 --dry-run --database-url "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
  python scripts/p98_discover_missing_major_publisher_volumes.py --publisher Marvel --limit-pages 5 --apply --database-url "..."
  python scripts/p98_discover_missing_major_publisher_volumes.py --all-major --limit-pages 10 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    ComicVineUniverseDiscoveryClient,
)
from app.services.p98_major_publisher_registry import resolve_major_publisher  # noqa: E402
from app.services.p98_missing_volume_discovery_service import (  # noqa: E402
    discover_missing_major_publishers,
    discover_missing_volumes_for_publisher,
    load_discovery_progress,
    save_discovery_results,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _print_report(reports) -> None:
    _log("P98 MISSING MAJOR PUBLISHER VOLUMES")
    _log("")
    for report in reports:
        _log(f"Publisher: {report.publisher}")
        _log(f"  ComicVine volumes scanned: {report.comicvine_volumes_scanned}")
        _log(f"  Already in comicvine_volume_universe: {report.already_in_comicvine_universe}")
        _log(f"  Already in universe_volume (P98):   {report.already_in_universe}")
        _log(f"  In both tables:                     {report.in_both_tables}")
        _log(f"  Missing from P98 only (CV yes):     {report.missing_from_p98_only}")
        _log(f"  Missing from both:                  {report.missing_from_both}")
        _log(f"  Missing from universe (candidates): {report.missing_from_universe}")
        _log(f"  Would insert:                {report.would_insert}")
        if report.inserted:
            _log(f"  Inserted:                    {report.inserted}")
        if report.throttled:
            _log(f"  Throttled:                   YES")
        if report.error:
            _log(f"  Error:                       {report.error}")
        _log("")
        if report.missing_candidates:
            _log("  Top Missing Volumes:")
            _log(
                f"  {'Volume':<36} {'CV ID':>8} {'Year':>6} {'Issues':>7} {'Score':>8} Reason"
            )
            for cand in report.missing_candidates[:25]:
                _log(
                    f"  {cand.volume[:36]:<36} {cand.comicvine_volume_id:>8} "
                    f"{(cand.start_year or 0):>6} {cand.issue_count:>7} "
                    f"{cand.priority_score:>8} {cand.reason[:40]}"
                )
        _log("")

    _log("Summary by publisher:")
    for report in reports:
        _log(
            f"  {report.publisher}: scanned={report.comicvine_volumes_scanned} "
            f"existing_p98={report.already_in_universe} existing_cv={report.already_in_comicvine_universe} "
            f"missing_p98_only={report.missing_from_p98_only} missing_both={report.missing_from_both} "
            f"would_insert={report.would_insert} inserted={report.inserted}"
        )


def _write_csv(path: str, reports) -> None:
    import os

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "publisher",
                "volume",
                "comicvine_volume_id",
                "start_year",
                "issue_count",
                "priority_score",
                "reason",
                "recommended_action",
            ]
        )
        for report in reports:
            for cand in report.missing_candidates:
                writer.writerow(
                    [
                        cand.publisher,
                        cand.volume,
                        cand.comicvine_volume_id,
                        cand.start_year or "",
                        cand.issue_count,
                        cand.priority_score,
                        cand.reason,
                        cand.recommended_action,
                    ]
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 missing major-publisher volume discovery")
    parser.add_argument("--publisher", type=str, default=None)
    parser.add_argument("--all-major", action="store_true")
    parser.add_argument("--limit-pages", type=int, default=10)
    parser.add_argument("--limit-volumes", type=int, default=500)
    parser.add_argument("--min-issue-count", type=int, default=1)
    parser.add_argument("--apply", action="store_true", help="Insert volume skeleton rows (default: dry-run)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--csv", type=str, default=None)
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--max-requests-per-hour", type=int, default=150)
    parser.add_argument("--min-seconds-between-requests", type=float, default=4.0)
    parser.add_argument("--pause-hours-on-420", type=float, default=2.0)
    parser.add_argument("--stop-on-throttle", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    apply = bool(args.apply)
    dry_run = not apply

    if not args.all_major and not args.publisher:
        _log("Specify --publisher or --all-major (major publishers only; no broad crawl).")
        return 2

    database_url = resolve_p97_database_url(args.database_url)
    settings = get_settings()
    if not (settings.comicvine_api_key or "").strip():
        _log("COMICVINE_API_KEY is required for missing-volume discovery.")
        return 2

    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        budget = ComicVineRateBudget(
            session,
            max_requests_per_hour=int(args.max_requests_per_hour),
            min_seconds_between_requests=float(args.min_seconds_between_requests),
            pause_hours_on_420=float(args.pause_hours_on_420),
        )
        client = ComicVineUniverseDiscoveryClient(session, budget)
        progress = load_discovery_progress()

        if args.all_major:
            reports = discover_missing_major_publishers(
                session,
                client,
                limit_pages=args.limit_pages,
                limit_volumes=args.limit_volumes,
                min_issue_count=args.min_issue_count,
                apply=apply,
                stop_on_throttle=args.stop_on_throttle,
            )
        else:
            config = resolve_major_publisher(args.publisher or "")
            if config is None:
                _log(f"Unknown or non-major publisher: {args.publisher!r}")
                return 2
            reports = [
                discover_missing_volumes_for_publisher(
                    session,
                    client,
                    config,
                    limit_pages=args.limit_pages,
                    limit_volumes=args.limit_volumes,
                    min_issue_count=args.min_issue_count,
                    apply=apply,
                    stop_on_throttle=args.stop_on_throttle,
                    progress=progress,
                    resume=not args.no_resume,
                )
            ]

    save_discovery_results(reports)

    if args.csv:
        _write_csv(args.csv, reports)

    if args.json:
        print(
            json.dumps(
                {
                    "database": describe_database_url(database_url),
                    "dry_run": dry_run,
                    "reports": [r.as_dict() for r in reports],
                },
                indent=2,
            )
        )
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    _log("")
    _print_report(reports)
    if args.csv:
        _log(f"CSV written: {args.csv}")
    if dry_run:
        _log("")
        _log("(dry run — no universe rows inserted; pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
