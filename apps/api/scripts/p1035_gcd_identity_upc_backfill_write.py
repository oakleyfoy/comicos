"""P103.5 — GCD identity + UPC backfill write (existing catalog_issue only)."""
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
    load_resume_catalog_issue_ids,
    run_p1035_identity_write,
)
from gcd_pipeline_cli import (  # noqa: E402
    add_all_catalog_argument,
    add_confirm_write_argument,
    add_gcd_cache_arguments,
    add_json_argument,
    add_output_argument,
    add_publisher_year_scope_arguments,
    add_refresh_cache_argument,
    resolve_output_path,
)

DEFAULT_OUT = Path("data/p1035/gcd_identity_backfill_write.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="P103.5 GCD identity + UPC backfill write")
    add_all_catalog_argument(parser)
    add_publisher_year_scope_arguments(parser, publisher_required=False)
    parser.add_argument("--limit", type=int, required=True)
    add_confirm_write_argument(parser, required=True)
    add_gcd_cache_arguments(parser)
    add_refresh_cache_argument(parser)
    parser.add_argument("--resume-job", type=int, default=None)
    add_json_argument(parser)
    add_output_argument(parser, default=str(DEFAULT_OUT))
    args = parser.parse_args()

    filters = validate_enrichment_filters(
        write_batch=True,
        limit=args.limit,
        publisher=args.publisher,
        year=args.year,
        year_from=args.year_from,
        year_to=args.year_to,
        confirm_write=args.confirm_write,
        all_catalog=args.all,
    )
    if filters is None:
        return 1

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache)
    if not gcd_path.exists():
        print(f"GCD database not found: {gcd_path}", file=sys.stderr)
        return 1

    rollback: dict = {"upc_ids": [], "issue_snapshots": []}
    skip_ids: set[int] = set()

    with Session(get_engine()) as session:
        if args.refresh_cache or not cache_path.exists():
            ensure_catalog_cache(session, cache_path, refresh=True)
        if args.resume_job is not None:
            skip_ids = load_resume_catalog_issue_ids(session, args.resume_job)
        report = run_p1035_identity_write(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            rollback_collector=rollback,
            skip_issue_ids=skip_ids,
        )

    payload = {"report": report.to_json(), "rollback": rollback}
    out_path = resolve_output_path(args, DEFAULT_OUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(json.dumps(report.to_json(), indent=2))
        print(f"Full report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
