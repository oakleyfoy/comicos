"""P103.6 targeted GCD identity exception resolution (duplicate CV, P106 UPC, ambiguous+evidence)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import resolve_cache_path, resolve_gcd_path  # noqa: E402
from app.services.p1036_gcd_identity_exception_resolution_service import (  # noqa: E402
    run_p1036_exception_resolution,
    write_p1036_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P103.6 resolve P103.5 identity exceptions without weakening match rules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/p1036_gcd_identity_exception_resolve.py --limit 50\n"
            "  python scripts/p1036_gcd_identity_exception_resolve.py --confirm-write YES\n"
        ),
    )
    parser.add_argument(
        "--exceptions-dir",
        type=Path,
        default=Path("data/p1035/exceptions"),
        help="Directory with duplicate_cv_conflicts.csv, upc_conflicts.csv, ambiguous_matches.csv",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/p1036/resolution"),
        help="Output directory for p1036_resolution_report.json and remaining/* CSVs",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max rows per resolver (for dry runs)")
    parser.add_argument("--gcd-db", default=None, help="Override GCD SQLite path")
    parser.add_argument("--cache-db", default=None, help="Override P101 catalog cache SQLite path")
    parser.add_argument("--confirm-write", default=None, help="Must be YES to commit DB changes")
    parser.add_argument("--skip-duplicate-cv", action="store_true")
    parser.add_argument("--skip-upc", action="store_true")
    parser.add_argument("--skip-ambiguous", action="store_true")
    args = parser.parse_args()

    dry_run = args.confirm_write != "YES"
    if not dry_run:
        print("P103.6 write mode: DB updates enabled.", file=sys.stderr)

    gcd_path = resolve_gcd_path(args.gcd_db)
    if not gcd_path.is_file():
        print(f"GCD database not found: {gcd_path}", file=sys.stderr)
        return 1
    cache_path = resolve_cache_path(args.cache_db)
    if not cache_path.is_file():
        print(f"Catalog cache not found: {cache_path}", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        report = run_p1036_exception_resolution(
            session,
            exceptions_dir=args.exceptions_dir,
            gcd_path=gcd_path,
            cache_path=cache_path,
            dry_run=dry_run,
            limit=args.limit,
            enable_duplicate_cv=not args.skip_duplicate_cv,
            enable_upc=not args.skip_upc,
            enable_ambiguous=not args.skip_ambiguous,
        )

    summary_path = write_p1036_outputs(report, args.out_dir)
    counts = report.counts.to_dict()
    print(json.dumps({"dry_run": dry_run, "counts": counts, "report_path": str(summary_path)}, indent=2))
    print(
        f"resolved ambiguous={counts['ambiguous_resolved']} "
        f"still_ambiguous={counts['ambiguous_still_ambiguous']} "
        f"duplicate_cv_repaired={counts['duplicate_cv_repaired']} "
        f"upc_p106_resolved={counts['upc_p106_resolved']} "
        f"upc_review={counts['upc_review_required']}"
    )
    print(f"Remaining exception CSVs: {args.out_dir / 'remaining'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
