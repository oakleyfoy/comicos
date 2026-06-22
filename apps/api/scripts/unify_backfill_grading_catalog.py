"""Backfill grading_candidate.catalog_issue_id from inventory_copy.catalog_issue_id.

Usage (from apps/api):
  python scripts/unify_backfill_grading_catalog.py --dry-run
  python scripts/unify_backfill_grading_catalog.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session, col, select

from app.db.session import get_engine
from app.models import GradingCandidate, InventoryCopy


def backfill_grading_candidate_catalog(*, session: Session, dry_run: bool) -> dict[str, int]:
    candidates = session.exec(
        select(GradingCandidate).where(col(GradingCandidate.catalog_issue_id).is_(None))
    ).all()
    updated = 0
    skipped_no_copy = 0
    skipped_no_catalog = 0
    for row in candidates:
        cid = int(row.inventory_item_id)
        copy = session.get(InventoryCopy, cid)
        if copy is None:
            skipped_no_copy += 1
            continue
        if copy.catalog_issue_id is None:
            skipped_no_catalog += 1
            continue
        if not dry_run:
            row.catalog_issue_id = int(copy.catalog_issue_id)
            session.add(row)
        updated += 1
    if not dry_run and updated:
        session.commit()
    return {
        "candidates_scanned": len(candidates),
        "updated": updated,
        "skipped_no_copy": skipped_no_copy,
        "skipped_no_catalog_on_copy": skipped_no_catalog,
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill grading_candidate.catalog_issue_id.")
    parser.add_argument("--dry-run", action="store_true", help="Compute only; do not write to DB.")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        report = backfill_grading_candidate_catalog(session=session, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
