"""P103 enrichment write-batch (update-only; cap MAX_ENRICHMENT_WRITE_LIMIT)."""
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
from app.services.p103_gcd_enrichment_write_service import run_p103_enrichment_write_batch  # noqa: E402
from gcd_pipeline_cli import (  # noqa: E402
    add_confirm_write_argument,
    add_gcd_cache_arguments,
    add_json_argument,
    add_output_argument,
    add_publisher_year_scope_arguments,
    add_refresh_cache_argument,
    resolve_output_path,
)

DEFAULT_OUT = Path("data/p103/gcd_enrichment_write_batch.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="P103 enrichment write-batch")
    add_publisher_year_scope_arguments(parser, publisher_required=True)
    parser.add_argument("--limit", type=int, required=True)
    add_confirm_write_argument(parser, required=True)
    add_gcd_cache_arguments(parser)
    add_refresh_cache_argument(parser)
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
    )
    if filters is None:
        return 1

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache)
    rollback: dict = {"upc_ids": [], "issue_snapshots": []}

    with Session(get_engine()) as session:
        if args.refresh_cache or not cache_path.exists():
            ensure_catalog_cache(session, cache_path, refresh=True)
        report = run_p103_enrichment_write_batch(
            session,
            gcd_path=gcd_path,
            cache_path=cache_path,
            filters=filters,
            rollback_collector=rollback,
        )

    payload = {
        "report": report.to_json(),
        "rollback": rollback,
    }
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
