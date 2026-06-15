"""Build P97 volume issue import queue from comicvine_volume_universe.

Usage:
  python scripts/p97_build_volume_issue_import_queue.py
  python scripts/p97_build_volume_issue_import_queue.py --refresh-complete
  python scripts/p97_build_volume_issue_import_queue.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_volume_issue_import_queue_service import (  # noqa: E402
    build_volume_issue_import_queue,
    get_top_queued_volumes,
    get_top_queued_volumes_by_tier,
)
from p97_volume_issue_queue_format import append_top_volumes_by_tier, format_volume_row  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt(value: int) -> str:
    return f"{value:,}"


def _leader(label: str, value: str, *, width: int = 52) -> str:
    dots = max(1, width - len(label) - len(value))
    return f"{label}{'.' * dots}{value}"


def format_build_summary(result, *, top: list, by_tier: dict) -> str:
    lines = [
        "P97 VOLUME ISSUE IMPORT QUEUE BUILD",
        "",
        f"Discovered Volumes Scanned: {_fmt(result.discovered_volumes_scanned)}",
        f"Queue Rows Inserted: {_fmt(result.queue_rows_inserted)}",
        f"Queue Rows Updated: {_fmt(result.queue_rows_updated)}",
        f"Skipped Complete: {_fmt(result.skipped_complete)}",
        f"Skipped Protected: {_fmt(result.skipped_protected)}",
        f"Pending Queue Size: {_fmt(result.pending_queue_size)}",
        f"Total Missing Issues Queued: {_fmt(result.total_missing_issues_queued)}",
        "",
        "TOP 25 QUEUED VOLUMES (OVERALL)",
        "",
    ]
    for row in top:
        lines.append(format_volume_row(row))
    append_top_volumes_by_tier(lines, by_tier, limit=10)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build P97 volume issue import queue")
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--refresh-complete",
        action="store_true",
        help="Re-queue rows currently marked complete",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    try:
        with Session(engine) as session:
            result = build_volume_issue_import_queue(
                session, refresh_complete=bool(args.refresh_complete)
            )
            top = get_top_queued_volumes(session, limit=25)
            by_tier = get_top_queued_volumes_by_tier(session, limit_per_tier=10)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            **result.__dict__,
            "top_queued_volumes": [
                {
                    "comicvine_volume_id": row.comicvine_volume_id,
                    "name": row.name,
                    "publisher": row.publisher,
                    "missing_issue_count": row.missing_issue_count,
                    "priority_score": row.priority_score,
                    "launch_priority_tier": row.launch_priority_tier,
                    "status": row.status,
                }
                for row in top
            ],
            "top_queued_volumes_by_tier": {
                tier: [
                    {
                        "comicvine_volume_id": row.comicvine_volume_id,
                        "name": row.name,
                        "publisher": row.publisher,
                        "missing_issue_count": row.missing_issue_count,
                        "priority_score": row.priority_score,
                        "launch_priority_tier": row.launch_priority_tier,
                    }
                    for row in rows
                ]
                for tier, rows in by_tier.items()
            },
        }
        print(json.dumps(payload, separators=(",", ":")))
    else:
        print(format_build_summary(result, top=top, by_tier=by_tier))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
