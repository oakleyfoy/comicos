"""P103 — GCD catalog enrichment dry-run (impact report only).

Usage:
  cd apps/api
  python scripts/p103_gcd_catalog_enrichment_dryrun.py --publisher DC --year 2018 --refresh-cache
  python scripts/p103_gcd_catalog_enrichment_dryrun.py --publisher DC --year 2018 --limit 500 --benchmark
"""
from __future__ import annotations

import argparse
import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import ensure_catalog_cache, resolve_cache_path, resolve_gcd_path  # noqa: E402
from app.services.p103_gcd_catalog_enrichment_service import (  # noqa: E402
    run_p103_enrichment_dryrun,
    validate_enrichment_filters,
)
from gcd_pipeline_cli import (  # noqa: E402
    add_gcd_cache_arguments,
    add_json_argument,
    add_output_argument,
    add_publisher_year_scope_arguments,
    add_refresh_cache_argument,
    resolve_output_path,
)

DEFAULT_OUT = Path("data/p103/gcd_enrichment_dryrun.json")
BENCH_OUT = Path("data/p103/gcd_enrichment_dryrun_benchmark.json")


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_summary(payload: dict) -> None:
    print("=" * 72)
    print("P103 GCD CATALOG ENRICHMENT (DRY-RUN / IMPACT)")
    print("=" * 72)
    print(f"Mode: {payload.get('mode', 'dry_run')}")
    print(f"Elapsed: {payload['elapsed_seconds']:.1f}s")
    print(f"GCD: {payload['gcd_database']}")
    print(f"Cache: {payload['catalog_cache']}")
    print(f"Filters: {payload.get('filters')}")
    perf = payload.get("perf")
    if perf:
        print()
        print("Timing (seconds):")
        for key in (
            "cache_load_sec",
            "gcd_query_sec",
            "match_sec",
            "upc_plan_sec",
            "field_plan_sec",
            "conflict_plan_sec",
            "json_serialize_sec",
        ):
            if key in perf:
                print(f"  {key:<22} {perf[key]}")
        print(f"  catalog_rows_scanned   {perf.get('catalog_rows_scanned', 0)}")
        print(f"  gcd_rows_loaded        {perf.get('gcd_rows_loaded', 0)}")
    print()
    print(f"Catalog issues in scope:     {_fmt(int(payload['catalog_issues_in_scope']))}")
    print(f"Matched to GCD:              {_fmt(int(payload['matched_to_gcd']))}")
    print(f"Missing GCD ids:             {_fmt(int(payload['missing_gcd_ids']))}")
    print(f"Missing UPCs:                {_fmt(int(payload['missing_upc']))}")
    print(f"Missing dates:               {_fmt(int(payload['missing_dates']))}")
    print(f"Missing printing:            {_fmt(int(payload['missing_printing']))}")
    print(f"Missing variants:            {_fmt(int(payload['missing_variants']))}")
    print(f"Projected field updates:     {_fmt(int(payload['projected_field_updates']))}")
    print(f"Projected UPC inserts:       {_fmt(int(payload['projected_upc_inserts']))}")
    print(f"Conflicts:                   {_fmt(int(payload['conflicts']))}")
    print(f"Skipped (no GCD match):        {_fmt(int(payload['skipped_no_catalog_match']))}")
    print()
    print("Updates by field:")
    for k, v in sorted((payload.get("updates_by_field") or {}).items(), key=lambda x: -int(x[1])):
        print(f"  {k:<28} {_fmt(int(v))}")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="P103 GCD enrichment dry-run")
    add_publisher_year_scope_arguments(parser, publisher_required=True)
    parser.add_argument("--limit", type=int, default=None)
    add_gcd_cache_arguments(parser)
    add_refresh_cache_argument(parser)
    parser.add_argument("--slow-path", action="store_true", help="Use legacy per-row Postgres dry-run")
    parser.add_argument("--benchmark", action="store_true", help="Emit detailed timing breakdown")
    add_json_argument(parser)
    add_output_argument(parser, default=None)
    args = parser.parse_args()

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache)
    if not gcd_path.exists():
        print(f"GCD database not found: {gcd_path}", file=sys.stderr)
        return 1

    filters = validate_enrichment_filters(
        write_batch=False,
        limit=args.limit,
        publisher=args.publisher,
        year=args.year,
        year_from=args.year_from,
        year_to=args.year_to,
        confirm_write=None,
    )
    if filters is None:
        print("Invalid filters", file=sys.stderr)
        return 1

    default_out = BENCH_OUT if args.benchmark else DEFAULT_OUT
    out_path = resolve_output_path(args, default_out)

    with Session(get_engine()) as session:
        if args.refresh_cache or not cache_path.exists():
            ensure_catalog_cache(session, cache_path, refresh=True)
        report = run_p103_enrichment_dryrun(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            use_fast_path=not args.slow_path,
            benchmark=args.benchmark,
        )
    payload = report.to_json()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_summary(payload)
        print(f"Full report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
