"""P97 — Queue priority sanity report (report only; no scoring changes)."""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_queue_priority_sanity_service import (  # noqa: E402
    RECOMMENDED_NOTE,
    build_queue_priority_sanity_report,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Flag suspicious P97 queue priority rows")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        rows = build_queue_priority_sanity_report(session, top=args.top)

    if args.json:
        print(
            json.dumps(
                {
                    "database": describe_database_url(database_url),
                    "recommended_scoring_change": RECOMMENDED_NOTE,
                    "count": len(rows),
                    "rows": [r.as_dict() for r in rows],
                },
                indent=2,
            )
        )
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log("P97 QUEUE PRIORITY SANITY REPORT")
    _log("")
    _log(f"Suspicious rows: {len(rows)}")
    _log("")
    for row in rows[:40]:
        _log(
            f"  {row.name[:40]:<40} missing={row.missing_issue_count:>4} "
            f"score={row.priority_score:.0f} core={row.is_core} — {row.reason}"
        )
    _log("")
    _log(f"Recommended scoring change: {RECOMMENDED_NOTE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
