"""Manually attach an approved GCD identity (and optional UPC) to a catalog issue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import resolve_gcd_path  # noqa: E402
from app.services.p1035_gcd_identity_exception_service import run_p1035_manual_attach  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P103.5 manual GCD identity attach (reviewed exception fix)",
        epilog=(
            "Example:\n"
            "  python scripts/p1035_gcd_identity_manual_attach.py "
            "--catalog-issue-id 12345 --gcd-issue-id 67890 --confirm-write YES"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--catalog-issue-id", type=int, required=True)
    parser.add_argument("--gcd-issue-id", type=int, required=True)
    parser.add_argument("--confirm-write", default=None, help="Must be YES")
    parser.add_argument(
        "--allow-upc-conflict",
        default=None,
        help="Must be YES to insert UPC when learned/mapped elsewhere (reviewed only)",
    )
    parser.add_argument("--gcd-db", default=None, help="Override GCD SQLite path")
    parser.add_argument("--output", type=Path, default=Path("data/p1035/manual_attach_result.json"))
    args = parser.parse_args()

    if args.confirm_write != "YES":
        print("Refusing without --confirm-write YES", file=sys.stderr)
        return 2

    gcd_path = resolve_gcd_path(args.gcd_db)
    if not gcd_path.exists():
        print(f"GCD database not found: {gcd_path}", file=sys.stderr)
        return 1

    rollback: dict = {"upc_ids": [], "issue_snapshots": []}
    try:
        with Session(get_engine()) as session:
            result = run_p1035_manual_attach(
                session,
                catalog_issue_id=int(args.catalog_issue_id),
                gcd_issue_id=int(args.gcd_issue_id),
                gcd_path=gcd_path,
                allow_upc_conflict=args.allow_upc_conflict == "YES",
                rollback_collector=rollback,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {"result": result, "rollback": rollback}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Rollback snapshot: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
