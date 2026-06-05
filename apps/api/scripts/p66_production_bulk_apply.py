"""Production bulk apply for remaining P66 HIGH-confidence backfill rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.services.printing_backfill import run_backfill
from app.services.printing_intelligence import (
    PRINTING_KIND_FIRST,
    resolve_printing_schedule,
)

# Prior production applies (Tigress pilot + 10-issue sample).
PRIOR_APPLIED_ISSUE_IDS = {1278, 7, 40, 38, 79, 132, 161, 391, 459, 462, 681}


def verify_applied_issue(issue: ReleaseIssue, variants: list[ReleaseVariant], before_issue: dict) -> dict:
    sched = resolve_printing_schedule(issue, variants)
    reprint_rows = [v for v in variants if (v.printing_kind or PRINTING_KIND_FIRST) != PRINTING_KIND_FIRST]
    printing_populated = all(
        v.printing_release_date is not None or v.printing_foc_date is not None for v in reprint_rows
    ) if reprint_rows else True

    polluted = False
    for v in reprint_rows:
        if (
            v.printing_release_date
            and issue.release_date == v.printing_release_date
            and issue.original_release_date != issue.release_date
        ):
            polluted = True
        if v.printing_foc_date and issue.foc_date == v.printing_foc_date:
            polluted = True

    orig_before = before_issue.get("original_release_date")
    orig_after = issue.original_release_date.isoformat() if issue.original_release_date else None
    rel_after = issue.release_date.isoformat() if issue.release_date else None
    if orig_before and orig_after != orig_before:
        first_preserved = False
    elif orig_after and rel_after and orig_after != rel_after:
        first_preserved = False
    else:
        first_preserved = True

    return {
        "issue_id": int(issue.id or 0),
        "pollution_on_issue_row": polluted,
        "reprint_variant_printing_populated": printing_populated,
        "schedule_badge": sched.printing_badge,
        "first_print_preserved": first_preserved,
        "issue_release_date": rel_after,
        "issue_foc_date": issue.foc_date.isoformat() if issue.foc_date else None,
        "original_release_date": orig_after,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-user-id", type=int, default=1)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    engine = get_engine()
    report: dict = {"owner_user_id": args.owner_user_id, "prior_applied_excluded": sorted(PRIOR_APPLIED_ISSUE_IDS)}

    try:
        with Session(engine) as session:
            if args.apply:
                with session.begin():
                    report["backfill"] = run_backfill(
                        session,
                        owner_user_id=args.owner_user_id,
                        apply=True,
                        force=False,
                        high_confidence_only=True,
                        exclude_issue_ids=PRIOR_APPLIED_ISSUE_IDS,
                        omit_proposals=True,
                    )
            else:
                report["backfill"] = run_backfill(
                    session,
                    owner_user_id=args.owner_user_id,
                    apply=False,
                    high_confidence_only=True,
                    exclude_issue_ids=PRIOR_APPLIED_ISSUE_IDS,
                    omit_proposals=True,
                )
    except Exception as exc:
        report["fatal_error"] = str(exc)
        print(json.dumps(report, indent=2, default=str))
        return 1

    if args.apply:
        applied_rows = report["backfill"].get("applied") or []
        verify: list[dict] = []
        failures: list[dict] = []
        with Session(engine) as session:
            for row in applied_rows:
                iid = int(row["release_issue_id"])
                issue = session.get(ReleaseIssue, iid)
                if issue is None:
                    failures.append({"issue_id": iid, "reason": "issue_missing"})
                    continue
                variants = list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == iid)).all())
                before_issue = (row.get("before") or {}).get("issue") or {}
                v = verify_applied_issue(issue, variants, before_issue)
                verify.append(v)
                if v["pollution_on_issue_row"] or not v["reprint_variant_printing_populated"] or not v["first_print_preserved"]:
                    failures.append(v)

        report["verification"] = {
            "checked": len(verify),
            "failures": failures,
            "all_passed": len(failures) == 0,
        }

    text = json.dumps(report, indent=2, default=str)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if not report.get("fatal_error") else 1


if __name__ == "__main__":
    sys.exit(main())
