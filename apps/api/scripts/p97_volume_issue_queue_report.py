"""P97 volume issue import queue analytics report.

Usage:
  python scripts/p97_volume_issue_queue_report.py
  python scripts/p97_volume_issue_queue_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_volume_issue_import_queue_service import get_volume_issue_queue_report  # noqa: E402
from app.services.p97_queue_priority_config import is_core_run  # noqa: E402
from p97_volume_issue_queue_format import (  # noqa: E402
    append_top_volumes_by_tier,
    format_volume_row,
    format_volume_row_header,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt(value: int) -> str:
    return f"{value:,}"


def _leader(label: str, value: str, *, width: int = 52) -> str:
    dots = max(1, width - len(label) - len(value))
    return f"{label}{'.' * dots}{value}"


def format_report(report) -> str:
    lines = [
        "P97 VOLUME ISSUE IMPORT QUEUE",
        "",
        f"Pending: {_fmt(report.pending)}",
        f"Running: {_fmt(report.running)}",
        f"Complete: {_fmt(report.complete)}",
        f"Failed: {_fmt(report.failed)}",
        f"Skipped: {_fmt(report.skipped)}",
        "",
        f"Total Missing Issues Queued: {_fmt(report.total_missing_issues_queued)}",
        "",
        "TOP QUEUED VOLUMES BY PRIORITY (OVERALL)",
        "",
        format_volume_row_header(),
        "",
    ]
    for row in report.top_volumes:
        lines.append(format_volume_row(row))
    append_top_volumes_by_tier(lines, report.top_volumes_by_tier, limit=10)
    lines.extend(["", "TOP PUBLISHERS BY QUEUED MISSING ISSUES", ""])
    for publisher, volume_count, missing in report.top_publishers[:15]:
        lines.append(_leader(publisher[:22], f"{_fmt(missing)} ({volume_count} vol)"))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 volume issue import queue report")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    try:
        with Session(engine) as session:
            report = get_volume_issue_queue_report(session)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "pending": report.pending,
            "running": report.running,
            "complete": report.complete,
            "failed": report.failed,
            "skipped": report.skipped,
            "total_missing_issues_queued": report.total_missing_issues_queued,
            "top_volumes_by_tier": {
                tier: [
                    {
                        "comicvine_volume_id": row.comicvine_volume_id,
                        "name": row.name,
                        "publisher": row.publisher,
                        "missing_issue_count": row.missing_issue_count,
                        "count_of_issues": row.count_of_issues,
                        "is_core_run": is_core_run(row.name),
                        "priority_score": row.priority_score,
                        "launch_priority_tier": row.launch_priority_tier,
                        "status": row.status,
                    }
                    for row in rows
                ]
                for tier, rows in report.top_volumes_by_tier.items()
            },
            "top_volumes": [
                {
                    "comicvine_volume_id": row.comicvine_volume_id,
                    "name": row.name,
                    "publisher": row.publisher,
                    "missing_issue_count": row.missing_issue_count,
                    "count_of_issues": row.count_of_issues,
                    "is_core_run": is_core_run(row.name),
                    "priority_score": row.priority_score,
                    "launch_priority_tier": row.launch_priority_tier,
                    "status": row.status,
                }
                for row in report.top_volumes
            ],
            "top_publishers": [
                {"publisher": pub, "volume_count": count, "missing_issues": missing}
                for pub, count, missing in report.top_publishers
            ],
        }
        print(json.dumps(payload, separators=(",", ":")))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
