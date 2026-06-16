"""P98 -> P97 promotion CLI (dry-run by default; --apply to write).

Reads data/p98/major_publisher_action_queue.json and promotes ONLY
IMPORT_CATALOG_METADATA rows into the P97 issue import queue. No ComicVine
calls, no imports, no deletions.

Examples:
  python scripts/p98_promote_gap_volumes_to_p97_queue.py            # dry run
  python scripts/p98_promote_gap_volumes_to_p97_queue.py --apply    # write queue
"""

from __future__ import annotations

import argparse
import json
import os

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_p97_promotion_service import promote_import_rows  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_IN = "data/p98/major_publisher_action_queue.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 -> P97 queue promotion")
    parser.add_argument("--queue", type=str, default=DEFAULT_IN, help="Action queue JSON path")
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    parser.add_argument("--database-url", type=str, default=None)
    args = parser.parse_args()

    queue_path = os.path.abspath(args.queue)
    if not os.path.isfile(queue_path):
        print(f"Action queue not found: {args.queue}")
        print("Run p98_generate_major_publisher_action_queue.py first.")
        return
    with open(queue_path, encoding="utf-8") as fh:
        rows = json.load(fh)

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        result = promote_import_rows(session, rows, apply=args.apply)

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"P98 -> P97 PROMOTION ({mode})")
    print(f"(database: {describe_database_url(database_url)})")
    print(f"  Queue rows considered:      {result.considered}")
    print(f"  Promotable (IMPORT_*):      {result.promotable}")
    print(f"  {'Created' if args.apply else 'Would create'}:{'':<14}{result.created}")
    print(f"  {'Updated' if args.apply else 'Would update'}:{'':<14}{result.updated}")
    print(f"  Skipped (non-pending):      {result.skipped_non_pending}")
    if not args.apply:
        print("  (dry run — P97 queue not modified; pass --apply to write)")


if __name__ == "__main__":
    main()
