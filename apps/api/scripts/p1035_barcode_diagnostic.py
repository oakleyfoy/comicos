"""P103.5 — per-barcode diagnostic (catalog_upc, learned, GCD, P103.5 skip reason).

Usage:
  cd apps/api
  python scripts/p1035_barcode_diagnostic.py \\
    --barcode 76194134194901111 \\
    --barcode 76194134349501111 \\
    --barcode 76194134349500311
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
from app.services.p1035_barcode_diagnostic_service import (  # noqa: E402
    build_p1035_barcode_diagnostic_context,
    diagnose_barcode,
)
from gcd_pipeline_cli import add_gcd_cache_arguments, add_json_argument, add_refresh_cache_argument  # noqa: E402

DEFAULT_EXCEPTION_DIR = Path("data/p1035/exceptions")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _print_report(results: list[dict]) -> None:
    for item in results:
        print("=" * 72)
        print(f"Barcode: {item['barcode_raw']} (normalized: {item['normalized_barcode']})")
        print(f"  In catalog_upc: {_yes_no(item['in_catalog_upc'])}", end="")
        if item.get("catalog_upc_issue_id") is not None:
            print(f"  issue_id={item['catalog_upc_issue_id']}", end="")
        print()
        print(f"  In learned_barcode: {_yes_no(item['in_learned_barcode'])}", end="")
        if item.get("learned_barcode_issue_id") is not None:
            print(f"  issue_id={item['learned_barcode_issue_id']} source={item.get('learned_barcode_source')}", end="")
        print()
        print(f"  Present in GCD: {_yes_no(item['in_gcd'])}")
        for m in item.get("gcd_matches") or []:
            print(
                f"    gcd_issue_id={m.get('gcd_issue_id')} "
                f"{m.get('publisher')} | {m.get('series')} #{m.get('issue_number')} "
                f"catalog_issue_id={m.get('catalog_issue_id_resolved')}"
            )
        match = item.get("matching_catalog_issue")
        if match:
            print(
                f"  Matching catalog_issue: yes  id={match.get('issue_id')} "
                f"#{match.get('issue_number')} gcd_id={match.get('gcd_issue_id')} "
                f"title={match.get('title')!r}"
            )
        else:
            print("  Matching catalog_issue: no")
        skipped = item.get("p1035_skipped")
        category = item.get("p1035_skip_category")
        detail = item.get("p1035_skip_detail")
        if skipped:
            print(f"  Skipped by P103.5: yes  reason={category}", end="")
            if detail:
                print(f"  ({detail})", end="")
            print()
        else:
            print("  Skipped by P103.5: no  (eligible for identity backfill)")
        hits = item.get("exception_backlog_hits") or []
        if hits:
            print(f"  Exception backlog files: {', '.join(h['file'] for h in hits)}")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="P103.5 barcode diagnostic")
    parser.add_argument("--barcode", action="append", required=True, help="Barcode (repeatable)")
    add_gcd_cache_arguments(parser)
    add_refresh_cache_argument(parser)
    parser.add_argument(
        "--exception-dir",
        default=str(DEFAULT_EXCEPTION_DIR),
        help="Optional P103.5 exception export directory to cross-check",
    )
    add_json_argument(parser)
    args = parser.parse_args()

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache)
    if not gcd_path.exists():
        print(f"GCD database not found: {gcd_path}", file=sys.stderr)
        return 1

    exception_dir = Path(args.exception_dir)
    if not exception_dir.is_dir():
        exception_dir = None

    engine = get_engine()
    with Session(engine) as session:
        if args.refresh_cache:
            ensure_catalog_cache(session, cache_path)
        diag_ctx = build_p1035_barcode_diagnostic_context(
            gcd_path=gcd_path,
            cache_path=cache_path,
            exception_dir=exception_dir,
        )
        results = [diagnose_barcode(session, bc, diag_ctx) for bc in args.barcode]

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        _print_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
