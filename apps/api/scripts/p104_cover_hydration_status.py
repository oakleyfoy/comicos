"""Print P104 cover hydration table presence, queue counts, and latest run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.p104_cover_hydration_status_service import collect_p104_cover_hydration_status  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _print_human_report(payload: dict) -> None:
    tables = payload.get("tables") or {}
    print("P104 cover hydration status")
    print(f"  catalog_cover_assets exists: {tables.get('catalog_cover_assets')}")
    print(f"  catalog_cover_hydration_runs exists: {tables.get('catalog_cover_hydration_runs')}")
    if payload.get("alembic_version"):
        print(f"  alembic_version: {payload['alembic_version']}")

    if payload.get("tables_missing"):
        print("")
        print(f"WARNING: {payload.get('warning')}")
        if payload.get("missing_tables"):
            print(f"  missing: {', '.join(payload['missing_tables'])}")
        return

    totals = payload.get("totals") or {}
    print("")
    print("Asset totals:")
    print(f"  pending:  {totals.get('pending', 0)}")
    print(f"  complete: {totals.get('complete', 0)}")
    print(f"  failed:   {totals.get('failed', 0)}")
    print(f"  other:    {totals.get('other', 0)}")
    print(f"  all:      {totals.get('all_assets', 0)}")

    by_status = payload.get("status_by_asset") or {}
    if by_status:
        print("")
        print("Counts by status:")
        for status, count in sorted(by_status.items()):
            print(f"  {status}: {count}")

    latest = payload.get("latest_hydration_run")
    print("")
    if latest:
        print(
            f"Latest hydration run: id={latest.get('id')} mode={latest.get('mode')} "
            f"status={latest.get('status')} completed={latest.get('completed')} "
            f"failed={latest.get('failed')} asset_pending={totals.get('pending', 0)}"
        )
    else:
        print("Latest hydration run: (none)")


def main() -> int:
    parser = argparse.ArgumentParser(description="P104 cover hydration DB status")
    parser.add_argument("--database-url", default=None, help="Override DATABASE_URL")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    url = resolve_p97_database_url(args.database_url)
    if not url:
        settings = get_settings()
        url = settings.database_url
    engine = get_p97_engine(url)

    with Session(engine) as session:
        payload = collect_p104_cover_hydration_status(session)

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        _print_human_report(payload)

    return 1 if payload.get("tables_missing") else 0


if __name__ == "__main__":
    sys.exit(main())
