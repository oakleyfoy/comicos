"""Inventory catalog unification - Phase 3: backfill catalog_issue_id on copies.

Usage (from apps/api):
  python scripts/unify_backfill_catalog_issue.py --dry-run
  python scripts/unify_backfill_catalog_issue.py --email user@example.com --dry-run
  python scripts/unify_backfill_catalog_issue.py --email user@example.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.catalog_backfill_service import (
    backfill_catalog_links,
    backfill_order_provenance,
)


def _resolve_user_id(session: Session, email: str | None) -> int | None:
    if not email:
        return None
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or user.id is None:
        raise SystemExit(f"No user found for email {email!r}")
    return int(user.id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill catalog_issue_id on inventory copies.")
    parser.add_argument("--email", default=None, help="Limit to copies owned by this user email.")
    parser.add_argument("--dry-run", action="store_true", help="Compute only; do not write to DB.")
    parser.add_argument(
        "--provenance",
        action="store_true",
        help="Also snapshot order financial provenance onto inventory_copy (Phase 4).",
    )
    args = parser.parse_args()

    with Session(get_engine()) as session:
        user_id = _resolve_user_id(session, args.email)
        report = backfill_catalog_links(session, dry_run=args.dry_run, user_id=user_id)
        out = {"catalog_links": report.as_dict()}
        if args.provenance:
            prov = backfill_order_provenance(session, dry_run=args.dry_run, user_id=user_id)
            out["order_provenance"] = prov.as_dict()

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
