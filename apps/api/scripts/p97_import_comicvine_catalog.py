from __future__ import annotations

import argparse
import json
import logging
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter  # noqa: E402

ISSUE_IMPORT_ERROR = "ERROR: --import-issues requested but no issue import phase ran."


def _print_run_config(args: argparse.Namespace) -> None:
    config = {
        "volume_id": args.volume_id,
        "publisher": args.publisher,
        "series_name": args.series_name,
        "strict_publisher": args.strict_publisher,
        "min_start_year": args.min_start_year,
        "limit": args.limit,
        "import_issues": args.import_issues,
        "resume": args.resume,
        "offset": args.offset,
        "dry_run": args.dry_run,
        "international_editions_allowed": args.allow_international_editions,
    }
    print("run_config:")
    print(json.dumps(config, indent=2))


def _run_exact_volume_import(args: argparse.Namespace) -> int:
    importer = ComicVineCatalogImporter(
        dry_run=args.dry_run,
        rate_limit_seconds=args.sleep_seconds,
        allow_international_editions=args.allow_international_editions,
    )
    msg = importer.initialize_or_explain()
    if msg:
        print(msg)
        return 1
    with Session(get_engine()) as session:
        stats = importer.import_single_volume(
            session,
            comicvine_volume_id=args.volume_id,
            import_issues=args.import_issues,
        )
    summary = {
        "mode": "exact_volume",
        "volume_id": stats.volume_id,
        "series_created": stats.series_created,
        "series_updated": stats.series_updated,
        "issues_created": stats.created_issues,
        "issues_updated": stats.updated_issues,
        "cover_images_created": stats.cover_images_created,
        "cover_images_skipped": stats.cover_images_skipped,
        "estimated_issue_count": stats.estimated_issue_count,
        "api_requests_used": stats.api_requests_used,
        "failures": len(stats.failures),
        "throttled": stats.throttled,
    }
    print("exact_volume_summary:")
    print(json.dumps(summary, indent=2))
    # Stable key=value lines for runner/log parsing.
    print(f"volume_id={stats.volume_id}")
    print(f"series_created={stats.series_created}")
    print(f"series_updated={stats.series_updated}")
    print(f"issues_created={stats.created_issues}")
    print(f"issues_updated={stats.updated_issues}")
    print(f"cover_images_created={stats.cover_images_created}")
    print(f"cover_images_skipped={stats.cover_images_skipped}")
    print(f"api_requests_used={stats.api_requests_used}")
    print(f"failures={len(stats.failures)}")
    print(f"throttled={stats.throttled}")
    if stats.throttled:
        print("ERROR: ComicVine HTTP 420 throttle detected during exact volume import.", file=sys.stderr)
        return 4
    return 0 if not stats.failures else 1


def _issue_work_performed(stats) -> bool:
    return (
        stats.issue_import_volumes_attempted > 0
        or stats.created_issues > 0
        or stats.updated_issues > 0
        or stats.cover_images_created > 0
        or stats.processed > 0
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 ComicVine bulk catalog import (offline job; not scan-time)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--series-name", default=None)
    parser.add_argument(
        "--volume-id",
        type=int,
        default=None,
        help="Import exactly this ComicVine volume id (no publisher/series search, no adjacent scanning)",
    )
    parser.add_argument(
        "--publisher",
        default=None,
        help="ComicVine volumes filter publisher name (API filter=publisher:NAME)",
    )
    parser.add_argument(
        "--strict-publisher",
        action="store_true",
        help="Skip volumes whose publisher name does not match --publisher (client-side validation)",
    )
    parser.add_argument(
        "--import-issues",
        action="store_true",
        help="After volumes, run a separate volume_issues job (issues + pending cover rows)",
    )
    parser.add_argument(
        "--allow-international-editions",
        action="store_true",
        help="Allow international license publishers and regional editions (default: English/US-first gate)",
    )
    parser.add_argument(
        "--min-start-year",
        type=int,
        default=None,
        help="Only import volumes whose series start_year >= this (client-side filter while paginating). Use for modern backfills, e.g. --min-start-year 2010",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=None,
        help="Min seconds between ComicVine API calls (>= 1.0)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _print_run_config(args)
    if args.volume_id is not None:
        if args.publisher or args.series_name:
            print("--volume-id is exact-id only; do not combine with --publisher/--series-name", file=sys.stderr)
            return 2
        return _run_exact_volume_import(args)
    if args.strict_publisher and not args.publisher:
        print("--strict-publisher requires --publisher", file=sys.stderr)
        return 2
    importer = ComicVineCatalogImporter(
        dry_run=args.dry_run,
        rate_limit_seconds=args.sleep_seconds,
        allow_international_editions=args.allow_international_editions,
    )
    msg = importer.initialize_or_explain()
    if msg:
        print(msg)
        return 1
    with Session(get_engine()) as session:
        stats = importer.run_bulk_import(
            session,
            limit=args.limit,
            offset=args.offset,
            resume=args.resume,
            publisher_filter=args.publisher,
            series_name=args.series_name,
            strict_publisher=args.strict_publisher,
            import_issues=args.import_issues,
            min_start_year=args.min_start_year,
        )
    print(f"volume_job_id={stats.volume_job_id}")
    print(f"api_pages_fetched={stats.api_pages_fetched}")
    print(f"total_candidates_seen={stats.total_candidates_seen}")
    print(f"accepted_volumes={stats.accepted_volumes}")
    print(f"imported_series={stats.imported_series}")
    print(f"skipped_publisher={stats.skipped_non_matching_publisher}")
    print(f"skipped_quality_gate={stats.skipped_quality_gate}")
    print(f"final_offset={stats.final_offset}")
    print(f"failures={len(stats.failures)}")
    if args.import_issues:
        print(f"issue_job_id={stats.issue_job_id}")
        print(f"issue_import_ran={stats.issue_import_ran}")
        print(f"accepted_volumes_raw={stats.accepted_volumes_raw}")
        print(f"accepted_volumes_unique={stats.accepted_volumes_unique}")
        print(f"duplicate_volumes_removed={stats.duplicate_volumes_removed}")
        print(f"issue_imports_started={stats.issue_imports_started}")
        print(f"issue_imports_completed={stats.issue_imports_completed}")
        print(f"issue_import_volumes_attempted={stats.issue_import_volumes_attempted}")
        print(f"issues_created={stats.created_issues}")
        print(f"issues_updated={stats.updated_issues}")
        print(f"cover_images_created={stats.cover_images_created}")
        print(f"cover_images_skipped={stats.cover_images_skipped}")
        print(f"cover_images_skipped_no_url={stats.cover_images_skipped_no_url}")
        if not stats.issue_import_ran or not _issue_work_performed(stats):
            print(ISSUE_IMPORT_ERROR, file=sys.stderr)
            return 3
    print("publisher_distribution:")
    print(json.dumps(stats.publisher_distribution, indent=2))
    print("publisher_quality_summary:")
    print(json.dumps(stats.publisher_quality_summary, indent=2))
    return 0 if not stats.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
