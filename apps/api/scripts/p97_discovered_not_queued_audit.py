"""P97 — Audit discovered volumes with missing issues but no active queue row."""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_discovered_not_queued_service import build_discovered_not_queued_audit  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _print_rows(rows) -> None:
    _log("P97 DISCOVERED NOT QUEUED AUDIT")
    _log("")
    highlights = [r for r in rows if r.highlight_core]
    if highlights:
        _log("Core / highlighted titles:")
        for row in highlights:
            _log(
                f"  * {row.name} (id={row.comicvine_volume_id}) pub={row.publisher!r} "
                f"missing={row.missing_issue_count} queue={row.p97_queue_status or 'NONE'} "
                f"action={row.recommended_action}"
            )
        _log("")
    _log(f"Total gaps: {len(rows)}")
    _log("")
    _log(
        f"{'ID':>8}  {'Missing':>7}  {'Queue':<10}  {'P98':>3}  {'Name':<36}  Publisher"
    )
    for row in rows[:100]:
        p98 = "YES" if row.universe_volume_exists else "NO"
        mark = "*" if row.highlight_core else " "
        _log(
            f"{mark}{row.comicvine_volume_id:>7}  {row.missing_issue_count:>7}  "
            f"{(row.p97_queue_status or 'NONE'):<10}  {p98:>3}  {row.name[:36]:<36}  "
            f"{(row.publisher or '')[:24]}"
        )
    if len(rows) > 100:
        _log(f"... and {len(rows) - 100} more")


def main() -> int:
    parser = argparse.ArgumentParser(description="Discovered-not-queued volume audit")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--highlights-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        rows = build_discovered_not_queued_audit(
            session,
            highlights_only=args.highlights_only,
        )

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
    _print_rows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
