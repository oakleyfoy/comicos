"""Weekly incremental LoCG sync for newly available future release dates."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    args = parser.parse_args()

    if args.production and not os.environ.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required for --production", file=sys.stderr)
        return 1

    from sqlmodel import Session

    from app.db.session import get_engine
    from app.services.external_catalog.sync_service import sync_new_weeks

    with Session(get_engine()) as session:
        summary = sync_new_weeks(session, delay_seconds=args.delay_seconds)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
