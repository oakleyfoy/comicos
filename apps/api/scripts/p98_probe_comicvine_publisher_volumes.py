"""P98 — Raw ComicVine publisher volume probe (dual local membership).

Examples:
  python scripts/p98_probe_comicvine_publisher_volumes.py --publisher Marvel --limit-pages 1 --database-url "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
"""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    ComicVineRateBudget,
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
)
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    ComicVineUniverseDiscoveryClient,
)
from app.services.p98_discovery_integrity_service import probe_publisher_volumes  # noqa: E402
from app.services.p98_major_publisher_registry import resolve_major_publisher  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _print_report(report) -> None:
    _log("P98 COMICVINE PUBLISHER VOLUME PROBE")
    _log("")
    _log(f"Publisher: {report.publisher}")
    _log(f"ComicVine filter: {report.comicvine_filter}")
    if report.error:
        _log(f"Error: {report.error}")
        return
    _log(f"Total scanned: {report.total_scanned}")
    _log(f"Distinct ComicVine IDs: {report.distinct_comicvine_ids}")
    _log(f"Publisher names observed: {', '.join(report.publishers_observed) or '(none)'}")
    _log(f"In comicvine_volume_universe: {report.in_cv_universe}")
    _log(f"In universe_volume (P98): {report.in_p98_universe}")
    _log(f"Missing from both: {report.missing_from_both}")
    _log(f"Missing from P98 only (in CV universe): {report.missing_from_p98_only}")
    _log("")
    _log(
        f"{'CV ID':>8}  {'Name':<40} {'Publisher':<22} {'Yr':>4} {'Iss':>5}  "
        f"{'CV Univ':>7}  {'P98 Vol':>7}"
    )
    for row in report.rows:
        cv_flag = "YES" if row.in_comicvine_volume_universe else "NO"
        p98_flag = "YES" if row.in_universe_volume else "NO"
        _log(
            f"{row.comicvine_volume_id:>8}  {row.name[:40]:<40} "
            f"{(row.publisher_name or '')[:22]:<22} {(row.start_year or 0):>4} "
            f"{row.issue_count:>5}  {cv_flag:>7}  {p98_flag:>7}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe raw ComicVine publisher volume pages")
    parser.add_argument("--publisher", type=str, required=True)
    parser.add_argument("--limit-pages", type=int, default=1)
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    parser.add_argument(
        "--min-seconds-between-requests",
        type=float,
        default=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    )
    parser.add_argument("--pause-hours-on-420", type=float, default=DEFAULT_PAUSE_HOURS_ON_420)
    args = parser.parse_args()

    if resolve_major_publisher(args.publisher) is None:
        _log(f"Unknown or non-major publisher: {args.publisher!r}")
        return 2

    settings = get_settings()
    if not (settings.comicvine_api_key or "").strip():
        _log("COMICVINE_API_KEY is required for ComicVine probe.")
        return 2

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        budget = ComicVineRateBudget(
            session,
            max_requests_per_hour=int(args.max_requests_per_hour),
            min_seconds_between_requests=float(args.min_seconds_between_requests),
            pause_hours_on_420=float(args.pause_hours_on_420),
        )
        client = ComicVineUniverseDiscoveryClient(session, budget)
        report = probe_publisher_volumes(
            session,
            client,
            publisher=args.publisher,
            limit_pages=args.limit_pages,
        )

    if args.json:
        print(
            json.dumps(
                {
                    "database": describe_database_url(database_url),
                    **report.as_dict(),
                },
                indent=2,
            )
        )
        return 0 if not report.error else 1

    _log(f"(database: {describe_database_url(database_url)})")
    _print_report(report)
    return 0 if not report.error else 1


if __name__ == "__main__":
    sys.exit(main())
