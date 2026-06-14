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
        "publisher": args.publisher,
        "series_name": args.series_name,
        "strict_publisher": args.strict_publisher,
        "limit": args.limit,
        "import_issues": args.import_issues,
        "resume": args.resume,
        "offset": args.offset,
        "dry_run": args.dry_run,
        "international_editions_allowed": args.allow_international_editions,
    }
    print("run_config:")
    print(json.dumps(config, indent=2))


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
        "--sleep-seconds",
        type=float,
        default=None,
        help="Min seconds between ComicVine API calls (>= 1.0)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _print_run_config(args)
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
