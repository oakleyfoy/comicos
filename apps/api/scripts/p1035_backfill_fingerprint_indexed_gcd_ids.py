"""P103.5 — Backfill GCD ids on catalog_issue rows in the fingerprint index (identity only).

Usage:
  cd apps/api
  python scripts/p1035_backfill_fingerprint_indexed_gcd_ids.py --dry-run --limit 1000
  python scripts/p1035_backfill_fingerprint_indexed_gcd_ids.py --confirm-write YES --limit 5000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import (  # noqa: E402
    ensure_catalog_cache,
    resolve_cache_path,
    resolve_gcd_path,
)
from app.services.p1035_fingerprint_indexed_gcd_backfill_service import (  # noqa: E402
    format_fingerprint_indexed_gcd_backfill_report,
    run_fingerprint_indexed_gcd_backfill,
)
from gcd_pipeline_cli import (  # noqa: E402
    add_confirm_write_argument,
    add_gcd_cache_arguments,
    add_json_argument,
    add_output_argument,
    add_refresh_cache_argument,
    resolve_output_path,
)

DEFAULT_OUT = Path("data/p1035/fingerprint_indexed_gcd_backfill.json")
DEFAULT_AMBIGUOUS = Path("data/p1035/exceptions/fingerprint_indexed_ambiguous.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P103.5 GCD identity backfill for catalog_image_fingerprint rows missing GCD ids"
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not write catalog_issue rows")
    parser.add_argument("--limit", type=int, default=None, help="Max candidate rows to attempt this run")
    add_confirm_write_argument(parser, required=False)
    add_gcd_cache_arguments(parser)
    add_refresh_cache_argument(parser)
    add_output_argument(parser, default=str(DEFAULT_OUT))
    parser.add_argument(
        "--ambiguous-log",
        type=Path,
        default=DEFAULT_AMBIGUOUS,
        help="JSON file for ambiguous / duplicate-CV review rows",
    )
    add_json_argument(parser)
    args = parser.parse_args()

    dry_run = bool(args.dry_run)
    if not dry_run and args.confirm_write != "YES":
        print("Refusing write without --confirm-write YES (or pass --dry-run)", file=sys.stderr)
        return 2
    if dry_run and args.confirm_write == "YES":
        print("Ignoring --confirm-write when --dry-run is set", file=sys.stderr)

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache)
    if not gcd_path.exists():
        print(f"GCD database not found: {gcd_path}", file=sys.stderr)
        return 1

    with Session(get_engine()) as session:
        if args.refresh_cache or not cache_path.exists():
            ensure_catalog_cache(session, cache_path, refresh=True)
        report = run_fingerprint_indexed_gcd_backfill(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            dry_run=dry_run,
            limit=args.limit,
            ambiguous_log_path=args.ambiguous_log,
        )

    out_path = resolve_output_path(args.output, DEFAULT_OUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.to_json()
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(format_fingerprint_indexed_gcd_backfill_report(report))
        print(f"report_path: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
