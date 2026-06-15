"""Import ComicVine issues for one manually requested P97 volume.

Usage:
  python scripts/p97_import_requested_volume_issues.py --volume-id 123456
  python scripts/p97_import_requested_volume_issues.py --volume-id 123456 --limit 50
  python scripts/p97_import_requested_volume_issues.py --volume-id 123456 --dry-run
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
from app.services.p97_requested_volume_import_service import (  # noqa: E402
    import_requested_volume_issues,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import issues for one P97-requested ComicVine volume")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--volume-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max issues per API chunk (default 100)")
    parser.add_argument("--dry-run", action="store_true")
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

        result = import_requested_volume_issues(
            session,
            budget,
            importer,
            volume_id=int(args.volume_id),
            limit=args.limit,
            dry_run=bool(args.dry_run),
        )

    payload = {
        "volume_id": result.volume_id,
        "dry_run": result.dry_run,
        "throttled": result.throttled,
        "api_requests_used": result.api_requests_used,
        "created_issues": result.created_issues,
        "updated_issues": result.updated_issues,
        "queue_status": result.queue_status,
        "failures": result.failures,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        mode = "DRY RUN" if result.dry_run else "IMPORT"
        print(f"{mode} volume_id={result.volume_id}")
        print(f"  created_issues={result.created_issues} updated_issues={result.updated_issues}")
        print(f"  api_requests_used={result.api_requests_used} throttled={result.throttled}")
        if result.queue_status:
            print(f"  queue_status={result.queue_status}")
        if result.failures:
            print("  failures:")
            for line in result.failures[:10]:
                print(f"    - {line}")

    return 1 if result.failures and result.throttled else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
