"""Clear issue-level dates that still match reprint variant printing dates (multi-SKU edge case)."""

from __future__ import annotations

import argparse
import json
import sys

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.services.printing_intelligence import PRINTING_KIND_FIRST

RESIDUAL_FIX_ISSUE_IDS = [568, 1488]


def clear_residual(session: Session, issue_id: int) -> dict:
    issue = session.get(ReleaseIssue, issue_id)
    if issue is None:
        return {"issue_id": issue_id, "error": "not_found"}
    before = {
        "release_date": issue.release_date.isoformat() if issue.release_date else None,
        "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
    }
    variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)).all())
    changed = False
    for v in variants:
        if (v.printing_kind or PRINTING_KIND_FIRST) == PRINTING_KIND_FIRST:
            continue
        if v.printing_foc_date and issue.foc_date == v.printing_foc_date:
            issue.foc_date = None
            changed = True
        if (
            v.printing_release_date
            and issue.release_date == v.printing_release_date
            and issue.original_release_date != issue.release_date
        ):
            issue.release_date = None
            changed = True
    if changed:
        session.add(issue)
    after = {
        "release_date": issue.release_date.isoformat() if issue.release_date else None,
        "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
    }
    return {"issue_id": issue_id, "before": before, "after": after, "changed": changed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--issue-id", type=int, action="append", default=[])
    args = parser.parse_args()
    ids = args.issue_id or RESIDUAL_FIX_ISSUE_IDS
    engine = get_engine()
    report: dict = {"issue_ids": ids, "results": []}
    with Session(engine) as session:
        if args.apply:
            with session.begin():
                for iid in ids:
                    report["results"].append(clear_residual(session, iid))
        else:
            for iid in ids:
                report["results"].append(clear_residual(session, iid))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
