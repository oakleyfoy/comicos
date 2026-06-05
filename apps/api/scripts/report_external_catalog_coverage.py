"""Coverage report: external LoCG catalog vs owner ReleaseIssue crosswalk."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--email", default="")
    args = parser.parse_args()

    if args.production and not os.environ.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required for --production", file=sys.stderr)
        return 1

    from sqlmodel import Session

    from app.db.session import get_engine
    from app.services.external_catalog.crosswalk import build_coverage_report, rebuild_external_catalog_crosswalk
    from owner_lookup import resolve_owner_user_id

    with Session(get_engine()) as session:
        owner_user_id = 1
        if args.email:
            owner_user_id = resolve_owner_user_id(session, args.email)
        rebuild_external_catalog_crosswalk(session, owner_user_id=owner_user_id)
        report = build_coverage_report(session, owner_user_id=owner_user_id)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
