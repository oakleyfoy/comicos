"""Seed the P97 ComicVine known-good volume queue (idempotent, no duplicates).

Seeds from:
  A. Existing catalog series that already carry a ComicVine volume id.
  B. Recent known-good manual seeds (Amazing Spider-Man volumes 87154 / 56505 / 152139).

Usage:
  python scripts/p97_seed_known_good_volumes.py
  python scripts/p97_seed_known_good_volumes.py --json
  python scripts/p97_seed_known_good_volumes.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_volume_queue_service import seed_known_good_volumes  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed P97 ComicVine known-good volume queue (idempotent)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--json", action="store_true", help="Print the seed summary as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Compute the plan without writing rows")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    try:
        with Session(engine) as session:
            summary = seed_known_good_volumes(session, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: seed failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, separators=(",", ":")))
    else:
        print("P97 Known Good Volume Queue Seed")
        print("=" * 40)
        print(f"{'inserted':<22}{summary['inserted']:>8}")
        print(f"{'updated':<22}{summary['updated']:>8}")
        print(f"{'already_exists':<22}{summary['already_exists']:>8}")
        print(f"{'total_queue_pending':<22}{summary['total_queue_pending']:>8}")
        print(f"{'total_queue_imported':<22}{summary['total_queue_imported']:>8}")
        if summary.get("dry_run"):
            print("(dry-run: no rows written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
