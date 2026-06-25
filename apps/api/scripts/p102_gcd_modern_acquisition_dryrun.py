"""P102 — GCD modern catalog + barcode acquisition dry-run / controlled write-batch.

Usage:
  cd apps/api
  python scripts/p102_gcd_modern_acquisition_dryrun.py --refresh-cache
  python scripts/p102_gcd_modern_acquisition_dryrun.py --json

  # Controlled write (after review; not run by default):
  python scripts/p102_gcd_modern_acquisition_dryrun.py --write-batch \\
    --publisher DC --year 2018 --limit 100 --confirm-write YES --refresh-cache
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.p101_catalog_cache_service import DEFAULT_CACHE_PATH, export_catalog_cache  # noqa: E402
from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS, run_p102_gcd_modern_dryrun  # noqa: E402
from app.services.p102_gcd_modern_acquisition_write_service import (  # noqa: E402
    run_p102_write_batch,
    validate_write_batch_args,
)
from gcd_pipeline_cli import (  # noqa: E402
    add_confirm_write_argument,
    add_gcd_cache_arguments,
    add_json_argument,
    add_output_argument,
    add_refresh_cache_argument,
    resolve_output_path,
)

DEFAULT_GCD = Path(r"C:\comic-os-p41-feed\data\p101\current\2026-06-15.db")
OUT = Path("data/p102/gcd_modern_acquisition_dryrun.json")
WRITE_OUT = Path("data/p102/gcd_modern_acquisition_write_batch.json")


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_summary(payload: dict) -> None:
    print("=" * 72)
    print("P102 GCD MODERN CATALOG + BARCODE ACQUISITION (DRY-RUN)")
    print("=" * 72)
    print(f"Elapsed: {payload['elapsed_seconds']:.1f}s")
    print(f"GCD: {payload['gcd_database']}")
    print(f"Cache: {payload['catalog_cache']}")
    print(f"Scope: {payload['scope_years'][0]}-{payload['scope_years'][1]}  publishers={', '.join(payload['scope_publishers'])}")
    print()
    print(f"Total GCD rows in scope:        {_fmt(payload['total_gcd_rows_in_scope'])}")
    print(f"Already in ComicOS:             {_fmt(payload['already_in_comicos'])}")
    print(f"Missing (classified):             {_fmt(payload['classified_missing'])}")
    print(f"Clean primary candidates:         {_fmt(payload['clean_primary_candidate'])}")
    print(f"Candidates with barcode:          {_fmt(payload['candidates_with_barcode'])}")
    print(f"Projected catalog_issue inserts:  {_fmt(payload['projected_catalog_issue_inserts'])}")
    print(f"Projected catalog_upc inserts:    {_fmt(payload['projected_catalog_upc_inserts'])}")
    print(f"Conflicts:                        {_fmt(payload['conflicts'])}")
    print(f"Rejections (low_confidence):      {_fmt(payload['rejection_count'])}")
    print()
    print("By class:")
    for k, v in sorted((payload.get("by_class") or {}).items(), key=lambda x: -x[1]):
        print(f"  {k:<28} {_fmt(int(v))}")
    print()
    print("By publisher (clean / projected issues / projected upc):")
    for pub in FOCUS_PUBLISHERS:
        row = (payload.get("by_publisher") or {}).get(pub, {})
        print(
            f"  {pub:<12} clean={_fmt(int(row.get('clean_primary_candidate', 0)))} "
            f"issues={_fmt(int(row.get('projected_catalog_issue_inserts', 0)))} "
            f"upc={_fmt(int(row.get('projected_catalog_upc_inserts', 0)))}"
        )
    print("=" * 72)


def _print_write_summary(payload: dict) -> None:
    print("=" * 72)
    print("P102 GCD MODERN ACQUISITION (WRITE-BATCH)")
    print("=" * 72)
    print(f"Elapsed: {payload['elapsed_seconds']:.1f}s")
    f = payload.get("filters") or {}
    print(f"Publisher: {f.get('publisher')}  years: {f.get('year_from')}-{f.get('year_to')}  limit: {f.get('limit')}")
    print()
    print(f"Inserted issues:     {_fmt(int(payload.get('inserted_issues', 0)))}")
    print(f"Inserted UPCs:       {_fmt(int(payload.get('inserted_upcs', 0)))}")
    print(f"Skipped existing:    {_fmt(int(payload.get('skipped_existing', 0)))}")
    print(f"Skipped conflicts:   {_fmt(int(payload.get('skipped_conflicts', 0)))}")
    err = payload.get("errors") or []
    print(f"Errors:              {len(err)}")
    for line in err[:20]:
        print(f"  {line}")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="P102 GCD modern acquisition dry-run / write-batch")
    add_gcd_cache_arguments(parser, gcd_default=str(DEFAULT_GCD), cache_default=str(DEFAULT_CACHE_PATH))
    add_refresh_cache_argument(parser)
    add_json_argument(parser)
    add_output_argument(parser, default=None, help_text="Report JSON path (default depends on mode)")
    parser.add_argument("--write-batch", action="store_true", help="Controlled catalog write (requires safety flags)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--publisher", choices=FOCUS_PUBLISHERS, default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--year-from", type=int, default=None)
    parser.add_argument("--year-to", type=int, default=None)
    add_confirm_write_argument(parser)
    args = parser.parse_args()

    gcd_path = Path(args.gcd_db)
    cache_path = Path(args.cache)
    if not gcd_path.exists():
        print(f"GCD DB not found: {gcd_path}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    if args.refresh_cache or not cache_path.exists():
        print(f"Exporting ComicOS cache -> {cache_path}", file=sys.stderr)
        with Session(get_engine()) as session:
            export_catalog_cache(session, cache_path)

    if args.write_batch:
        try:
            filters = validate_write_batch_args(
                write_batch=True,
                limit=args.limit,
                publisher=args.publisher,
                year=args.year,
                year_from=args.year_from,
                year_to=args.year_to,
                confirm_write=args.confirm_write,
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        assert filters is not None
        out = resolve_output_path(args, WRITE_OUT)
        with Session(get_engine()) as session:
            report = run_p102_write_batch(
                session,
                gcd_path=gcd_path,
                cache_path=cache_path,
                filters=filters,
            )
        payload = report.to_json()
        payload["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
        payload["gcd_database"] = str(gcd_path)
        payload["catalog_cache"] = str(cache_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            _print_write_summary(payload)
            print(f"Full report: {out}")
        return 0

    report = run_p102_gcd_modern_dryrun(gcd_path=gcd_path, cache_path=cache_path)
    payload = report.to_json()
    payload["elapsed_seconds"] = round(time.perf_counter() - t0, 2)

    out = resolve_output_path(args, OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_summary(payload)
        print(f"Full report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
