"""P103.5 — GCD identity + UPC backfill dry-run (existing catalog_issue only).

Usage:
  cd apps/api
  python scripts/p1035_gcd_identity_upc_backfill_dryrun.py --publisher DC --year-from 2009 --year-to 2026 --limit 1000 --out data/p1035/dc_dryrun.json
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
from app.services.gcd_catalog_import_dashboard_service import ensure_catalog_cache, resolve_cache_path, resolve_gcd_path  # noqa: E402
from app.services.p103_gcd_catalog_enrichment_service import validate_enrichment_filters  # noqa: E402
from app.services.p1035_gcd_identity_backfill_service import (  # noqa: E402
    analyze_p1035_candidate_scope,
    format_p1035_candidate_scope_report,
    run_p1035_identity_dryrun,
)
from app.services.p1035_gcd_identity_exception_service import (  # noqa: E402
    P1035ExceptionCollector,
    format_p1035_exception_summary,
    write_p1035_exception_backlog,
)
from gcd_pipeline_cli import (  # noqa: E402
    add_all_catalog_argument,
    add_gcd_cache_arguments,
    add_json_argument,
    add_output_argument,
    add_publisher_year_scope_arguments,
    add_refresh_cache_argument,
    resolve_output_path,
)
from p1035_resume_cli import add_p1035_resume_job_argument, resolve_p1035_resume_skip_ids  # noqa: E402

DEFAULT_OUT = Path("data/p1035/gcd_identity_backfill_dryrun.json")
DEFAULT_EXCEPTION_DIR = Path("data/p1035/exceptions")


def _print_summary(payload: dict) -> None:
    print("=" * 72)
    print("P103.5 GCD IDENTITY + UPC BACKFILL (DRY-RUN)")
    print("=" * 72)
    print(f"Elapsed: {payload.get('elapsed_seconds', 0):.1f}s")
    print(f"Filters: {payload.get('filters')}")
    for label in (
        "existing_issues_scanned",
        "missing_gcd_ids",
        "matched_gcd_ids",
        "projected_upc_inserts",
        "ambiguous_skipped",
        "duplicate_cv_conflicts",
        "validation_failures",
        "learned_barcode_conflicts",
        "upc_elsewhere_conflicts",
    ):
        if label in payload:
            print(f"  {label}: {payload[label]:,}")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="P103.5 GCD identity + UPC backfill dry-run")
    add_all_catalog_argument(parser)
    add_publisher_year_scope_arguments(parser, publisher_required=False)
    parser.add_argument("--limit", type=int, default=None)
    add_gcd_cache_arguments(parser)
    add_refresh_cache_argument(parser)
    parser.add_argument("--benchmark", action="store_true")
    add_p1035_resume_job_argument(parser)
    add_json_argument(parser)
    add_output_argument(parser, default=str(DEFAULT_OUT))
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
        all_catalog=args.all,
    )
    if filters is None:
        print("Invalid filters", file=sys.stderr)
        return 1

    skip_ids: set[int] = set()
    with Session(get_engine()) as session:
        if args.refresh_cache or not cache_path.exists():
            ensure_catalog_cache(session, cache_path, refresh=True)
        skip_ids = resolve_p1035_resume_skip_ids(session, args.resume_job)
        scope_stats = analyze_p1035_candidate_scope(cache_path, filters, skip_ids)
        if not args.json:
            print(format_p1035_candidate_scope_report(scope_stats))
            print()
        collector = P1035ExceptionCollector()
        report = run_p1035_identity_dryrun(
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            benchmark=args.benchmark,
            skip_issue_ids=skip_ids,
            scope_stats=scope_stats,
            exception_collector=collector,
        )

    payload = report.to_json()
    if report.exceptions:
        exc_summary = write_p1035_exception_backlog(report.exceptions, DEFAULT_EXCEPTION_DIR)
        if not args.json:
            print(format_p1035_exception_summary(exc_summary))
            print()
    out_path = resolve_output_path(args, DEFAULT_OUT)
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
