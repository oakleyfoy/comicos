"""Search ComicVine and enqueue a manual P97 volume issue-import request.

Usage:
  python scripts/p97_request_comicvine_volume.py --query "Absolute Batman" --publisher "DC Comics"
  python scripts/p97_request_comicvine_volume.py --query "Absolute Batman" --volume-id 123456 --notes "scanner testing"
  python scripts/p97_request_comicvine_volume.py --volume-id 123456 --priority urgent
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    ComicVineUniverseDiscoveryClient,
)
from app.services.p97_manual_volume_request_service import (  # noqa: E402
    VolumeSearchCandidate,
    fetch_and_enqueue_manual_volume_request,
    search_comicvine_volumes_for_request,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _format_candidate(row: VolumeSearchCandidate) -> str:
    parts = [
        f"id={row.volume_id}",
        f"name={row.name!r}",
        f"publisher={row.publisher!r}",
        f"start_year={row.start_year}",
        f"count_of_issues={row.count_of_issues}",
    ]
    if row.site_detail_url:
        parts.append(f"url={row.site_detail_url}")
    return "  " + " | ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Request a ComicVine volume for P97 issue import")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--query", default=None, help="ComicVine volume search query")
    parser.add_argument("--publisher", default=None, help="Filter search results by publisher name")
    parser.add_argument("--volume-id", type=int, default=None, help="ComicVine volume id to enqueue")
    parser.add_argument(
        "--priority",
        default=None,
        choices=("urgent",),
        help="Mark manual request as urgent (higher queue score)",
    )
    parser.add_argument("--notes", default=None, help="Notes stored on the queue row")
    parser.add_argument("--search-limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.volume_id and not args.query:
        parser.error("Provide --query to search and/or --volume-id to enqueue")

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    urgent = args.priority == "urgent"

    with Session(engine) as session:
        budget = ComicVineRateBudget(
            session,
            max_requests_per_hour=DEFAULT_MAX_REQUESTS_PER_HOUR,
            min_seconds_between_requests=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
            pause_hours_on_420=DEFAULT_PAUSE_HOURS_ON_420,
        )
        client = ComicVineUniverseDiscoveryClient(session, budget)

        candidates: list[VolumeSearchCandidate] = []
        if args.query:
            candidates = search_comicvine_volumes_for_request(
                client,
                query=args.query,
                publisher=args.publisher,
                limit=args.search_limit,
            )

        if args.volume_id is None:
            if args.json:
                print(
                    json.dumps(
                        {
                            "query": args.query,
                            "publisher_filter": args.publisher,
                            "candidates": [
                                {
                                    "volume_id": c.volume_id,
                                    "name": c.name,
                                    "publisher": c.publisher,
                                    "start_year": c.start_year,
                                    "count_of_issues": c.count_of_issues,
                                    "site_detail_url": c.site_detail_url,
                                }
                                for c in candidates
                            ],
                        },
                        indent=2,
                    )
                )
            else:
                print("Matching ComicVine volumes:")
                if not candidates:
                    print("  (none)")
                for candidate in candidates:
                    print(_format_candidate(candidate))
            return 0

        result = fetch_and_enqueue_manual_volume_request(
            client,
            session,
            volume_id=int(args.volume_id),
            notes=args.notes,
            urgent=urgent,
        )
        row = result.queue_row
        payload = {
            "volume_id": result.volume_id,
            "universe_action": result.universe_action,
            "queue_action": result.queue_action,
            "queue": {
                "comicvine_volume_id": row.comicvine_volume_id,
                "name": row.name,
                "publisher": row.publisher,
                "status": row.status,
                "launch_priority_tier": row.launch_priority_tier,
                "priority_score": row.priority_score,
                "request_notes": row.request_notes,
                "missing_issue_count": row.missing_issue_count,
            },
            "search_candidates": [
                {
                    "volume_id": c.volume_id,
                    "name": c.name,
                    "publisher": c.publisher,
                    "start_year": c.start_year,
                    "count_of_issues": c.count_of_issues,
                    "site_detail_url": c.site_detail_url,
                }
                for c in candidates
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if args.query:
                print("Search results:")
                for candidate in candidates:
                    print(_format_candidate(candidate))
                print("")
            print(f"Enqueued volume {result.volume_id} ({result.queue_action}, universe {result.universe_action})")
            print(
                f"  tier={row.launch_priority_tier} score={row.priority_score} status={row.status} "
                f"missing={row.missing_issue_count}"
            )
            if row.request_notes:
                print(f"  notes={row.request_notes!r}")
            print("Run scripts/p97_import_requested_volume_issues.py to import issues.")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
