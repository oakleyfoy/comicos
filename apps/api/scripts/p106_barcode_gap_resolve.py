"""P106 — resolve barcode gaps via GCD exact barcode match.

Usage:
  cd apps/api
  python scripts/p106_barcode_gap_resolve.py --barcode 76194134349501111
  python scripts/p106_barcode_gap_resolve.py --barcode 76194134349501111 --confirm-write YES
  python scripts/p106_barcode_gap_resolve.py --from-scanner-queue --limit 100 --confirm-write YES
  python scripts/p106_barcode_gap_resolve.py --from-p1035-upc-conflicts data/p1035/exceptions/upc_conflicts.csv --limit 50 --dry-run
  python scripts/p106_barcode_gap_resolve.py --from-p1035-upc-conflicts data/p1035/exceptions/upc_conflicts.csv --limit 50 --confirm-write YES
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
    resolve_cache_path,
    resolve_gcd_path,
)
from app.services.p106_barcode_gap_resolver_service import (  # noqa: E402
    DEFAULT_P1035_BATCH_REPORT,
    diagnose_barcode_gap,
    resolve_barcode_gap,
    resolve_barcode_gaps_from_scanner_queue,
    resolve_p1035_upc_conflicts_from_csv,
)
from gcd_pipeline_cli import add_gcd_cache_arguments, add_json_argument  # noqa: E402


def _print_barcode_diagnosis(item: dict) -> None:
    if "diagnosis" in item:
        d = item["diagnosis"]
    else:
        d = item
    print(f"Barcode: {d.get('normalized_barcode') or d.get('searched_full_barcode')}")
    for key in (
        "searched_full_barcode",
        "searched_upc12",
        "searched_supplement",
        "gcd_exact_hits",
        "gcd_prefix_hits",
        "gcd_notes_hits",
        "gcd_lookup_final_reason",
        "final_reason",
        "reason",
        "status",
        "next_source",
        "ready_to_auto_import",
        "gcd_match_count",
    ):
        if key in d and d[key] not in (None, "", [], {}):
            print(f"  {key}: {d[key]}")


def _print_batch_summary(payload: dict) -> None:
    counts = payload.get("counts") or {}
    print("P106 P103.5 UPC conflict batch")
    print(f"  report: {payload.get('report_path')}")
    print(f"  dry_run: {payload.get('dry_run')}")
    for key in (
        "scanned",
        "auto_attached",
        "auto_imported",
        "already_resolved",
        "unresolved",
        "review_required",
        "conflicts",
        "errors",
    ):
        if key in counts:
            print(f"  {key}: {counts[key]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="P106 barcode gap resolver (GCD exact barcode)")
    parser.add_argument("--barcode", action="append", help="Barcode to diagnose or resolve")
    parser.add_argument("--from-scanner-queue", action="store_true", help="Process p105 missing-barcode queue")
    parser.add_argument(
        "--from-p1035-upc-conflicts",
        default=None,
        help="Batch-resolve P103.5 upc_conflicts.csv export",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true", help="Diagnose/preview only (no writes)")
    parser.add_argument("--confirm-write", default=None, help="Must be YES to write")
    parser.add_argument(
        "--report",
        default=str(DEFAULT_P1035_BATCH_REPORT),
        help="Batch report JSON path (P103.5 CSV mode)",
    )
    add_gcd_cache_arguments(parser)
    add_json_argument(parser)
    args = parser.parse_args()

    confirm = str(args.confirm_write or "").strip().upper() == "YES"
    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache)

    has_p1035 = bool(args.from_p1035_upc_conflicts)
    if not args.from_scanner_queue and not args.barcode and not has_p1035:
        parser.error("Provide --barcode, --from-scanner-queue, and/or --from-p1035-upc-conflicts")

    engine = get_engine()
    with Session(engine) as session:
        if has_p1035:
            csv_path = Path(args.from_p1035_upc_conflicts)
            if not csv_path.is_file():
                print(f"CSV not found: {csv_path}", file=sys.stderr)
                return 1
            payload = resolve_p1035_upc_conflicts_from_csv(
                session,
                csv_path=csv_path,
                gcd_path=gcd_path,
                cache_path=cache_path,
                limit=args.limit,
                confirm_write=confirm,
                dry_run=args.dry_run,
                report_path=Path(args.report),
            )
        elif args.from_scanner_queue:
            payload = resolve_barcode_gaps_from_scanner_queue(
                session,
                gcd_path=gcd_path,
                cache_path=cache_path,
                limit=args.limit,
                confirm_write=confirm and not args.dry_run,
            )
        else:
            results = []
            for bc in args.barcode or []:
                if confirm and not args.dry_run:
                    results.append(
                        resolve_barcode_gap(
                            session,
                            barcode=bc,
                            gcd_path=gcd_path,
                            cache_path=cache_path,
                            confirm_write=True,
                        )
                    )
                else:
                    results.append(
                        diagnose_barcode_gap(
                            session,
                            barcode=bc,
                            gcd_path=gcd_path,
                            cache_path=cache_path,
                        )
                    )
            payload = {"barcodes": results}

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    elif has_p1035:
        _print_batch_summary(payload)
    else:
        if args.from_scanner_queue:
            for outcome in payload.get("outcomes", []):
                _print_barcode_diagnosis(outcome.get("diagnosis") or outcome)
                print("-" * 40)
        else:
            for item in payload.get("barcodes", []):
                _print_barcode_diagnosis(item.get("diagnosis") or item)
                if item.get("written") is not None:
                    print(f"  written: {item['written']}")
                print("-" * 40)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
