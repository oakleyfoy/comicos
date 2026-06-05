"""P66 printing intelligence backfill — guarded apply.

Default is dry-run (no writes). Pass --apply to mutate the database.

Examples (from apps/api):
  python scripts/p66_apply_printing_backfill.py --owner-user-id 1
  python scripts/p66_apply_printing_backfill.py --owner-user-id 1 --issue-id 1278 --apply
  python scripts/p66_apply_printing_backfill.py --owner-user-id 1 --limit 10 --json-out ../../data/p66_backfill_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_engine
from app.services.printing_backfill import run_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="P66 printing backfill (dry-run by default)")
    parser.add_argument("--owner-user-id", type=int, default=None)
    parser.add_argument("--issue-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes (default: dry-run only)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting existing original_release_date/original_foc_date",
    )
    parser.add_argument("--json-out", type=str, default="")
    parser.add_argument(
        "--include-low-confidence",
        action="store_true",
        help="Apply low-confidence rows (not recommended)",
    )
    parser.add_argument(
        "--exclude-issue-id",
        type=int,
        action="append",
        default=[],
        help="Skip these release_issue ids (repeatable)",
    )
    parser.add_argument(
        "--omit-proposals",
        action="store_true",
        help="Omit full proposals array from JSON (smaller bulk reports)",
    )
    args = parser.parse_args()

    apply = bool(args.apply)
    if apply and args.force:
        print("warning: --force enables overwriting original_* dates", file=sys.stderr)

    exclude = set(args.exclude_issue_id or [])
    engine = get_engine()
    report: dict
    try:
        with Session(engine) as session:
            if apply:
                with session.begin():
                    report = run_backfill(
                        session,
                        owner_user_id=args.owner_user_id,
                        issue_id=args.issue_id,
                        limit=args.limit,
                        apply=True,
                        force=args.force,
                        high_confidence_only=not args.include_low_confidence,
                        exclude_issue_ids=exclude or None,
                        omit_proposals=args.omit_proposals,
                    )
            else:
                report = run_backfill(
                    session,
                    owner_user_id=args.owner_user_id,
                    issue_id=args.issue_id,
                    limit=args.limit,
                    apply=False,
                    force=False,
                    high_confidence_only=not args.include_low_confidence,
                    exclude_issue_ids=exclude or None,
                    omit_proposals=args.omit_proposals,
                )
    except Exception as exc:
        print(json.dumps({"dry_run": not apply, "apply": apply, "fatal_error": str(exc)}, indent=2))
        return 1

    text = json.dumps(report, indent=2, default=str)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
