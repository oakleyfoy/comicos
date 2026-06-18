"""P98 — Repair foreign / wrong publisher matches (dry-run default)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_publisher_match_repair_service import (  # noqa: E402
    apply_publisher_match_repairs,
    build_publisher_match_repairs,
    save_publisher_match_rule_analysis,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 publisher match repair")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--apply", action="store_true", help="Mark superseded P98 universe volumes")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dry_run = not args.apply
    save_publisher_match_rule_analysis()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        repairs = build_publisher_match_repairs(session)
        result = apply_publisher_match_repairs(session, repairs, dry_run=dry_run)

    if args.json:
        print(json.dumps({"database": describe_database_url(database_url), **result.as_dict()}, indent=2))
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    _log("")
    for row in repairs:
        _log(f"Volume: {row.volume_name}")
        _log(f"  Current Publisher: {row.current_publisher}")
        _log(f"  Proposed Publisher: {row.proposed_publisher}")
        if row.proposed_volume_id is not None:
            _log(f"  Canonical Volume ID: {row.proposed_volume_id}")
        _log(f"  Reason: {row.reason}")
        _log("")
    _log(f"Universe volumes superseded: {result.superseded_universe_volumes}")
    if dry_run:
        _log("Dry-run only — pass --apply to mark foreign_superseded on P98 universe volumes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
