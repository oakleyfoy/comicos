"""P97 — Core run publisher mismatch report."""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_core_publisher_mismatch_service import (  # noqa: E402
    build_core_publisher_mismatch_report,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Core title publisher mismatch report")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        rows = build_core_publisher_mismatch_report(session)

    if args.json:
        print(
            json.dumps(
                {
                    "database": describe_database_url(database_url),
                    "count": len(rows),
                    "rows": [r.as_dict() for r in rows],
                },
                indent=2,
            )
        )
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log("P97 CORE PUBLISHER MISMATCH REPORT")
    _log("")
    if not rows:
        _log("No mismatches detected for core report labels.")
        return 0
    for row in rows:
        _log(f"Title: {row.core_title}")
        _log(f"  Expected publisher: {row.expected_publisher}")
        _log(f"  Matched publisher:  {row.matched_publisher}")
        _log(f"  Volume: {row.volume_name} (id={row.volume_id})")
        _log(f"  Status: {row.status}")
        _log(f"  Recommended: {row.recommended_action}")
        _log("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
