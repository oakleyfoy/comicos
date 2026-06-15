"""P97-23A ComicVine universe analytics report (read-only).

Usage:
  python scripts/p97_universe_analytics_report.py
  python scripts/p97_universe_analytics_report.py --top-volumes 50
  python scripts/p97_universe_analytics_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_comicvine_universe_analytics_service import (  # noqa: E402
    get_universe_analytics_report,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt(value: int) -> str:
    return f"{value:,}"


def _leader(label: str, value: str, *, width: int = 52) -> str:
    dots = max(1, width - len(label) - len(value))
    return f"{label}{'.' * dots}{value}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def format_report(report, *, top_volumes: int = 25, top_publishers: int = 15) -> str:
    lines = [
        "P97 COMICVINE UNIVERSE ANALYTICS",
        "",
        f"Total Discovered Volumes: {_fmt(report.total_discovered_volumes)}",
        f"Total Discoverable Issues: {_fmt(report.total_discoverable_issues)}",
        "",
        f"Current ComicOS Catalog: {_fmt(report.current_catalog_issues)}",
        f"Projected Catalog Ceiling: {_fmt(report.projected_comicos_catalog_ceiling)}",
        "",
        f"Direct CV-Linked Existing Issues: {_fmt(report.direct_cv_linked_existing_issues)}",
        f"Estimated Matched Existing Issues: {_fmt(report.estimated_matched_existing_issues)}",
        f"Issues Not Yet In Catalog: {_fmt(report.issues_not_yet_in_catalog)}",
        f"Unmatched Discovered Issue Ceiling: {_fmt(report.unmatched_discovered_issue_ceiling)}",
        f"Coverage Percent: {_fmt_pct(report.coverage_percent)}",
        "",
        f"LARGEST VOLUMES (top {top_volumes})",
        "",
    ]
    for row in report.largest_volumes[:top_volumes]:
        label = (row.name or f"Volume {row.volume_id}")[:26]
        lines.append(_leader(label, _fmt(row.count_of_issues)))
    lines.extend(["", f"TOP PUBLISHERS BY ISSUE COUNT (top {top_publishers})", ""])
    for row in report.top_publishers[:top_publishers]:
        lines.append(_leader(row.publisher[:26], _fmt(row.total_issues)))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 ComicVine universe analytics")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--top-volumes", type=int, default=25, help="Rows to print (fetch up to 1000)")
    parser.add_argument("--top-publishers", type=int, default=15)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    try:
        with Session(engine) as session:
            report = get_universe_analytics_report(
                session,
                top_volumes_limit=max(1000, args.top_volumes),
                top_publishers_limit=max(args.top_publishers, 100),
            )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        payload = {
            "total_discovered_volumes": report.total_discovered_volumes,
            "total_discoverable_issues": report.total_discoverable_issues,
            "current_catalog_issues": report.current_catalog_issues,
            "projected_comicos_catalog_ceiling": report.projected_comicos_catalog_ceiling,
            "direct_cv_linked_existing_issues": report.direct_cv_linked_existing_issues,
            "estimated_matched_existing_issues": report.estimated_matched_existing_issues,
            "issues_not_yet_in_catalog": report.issues_not_yet_in_catalog,
            "unmatched_discovered_issue_ceiling": report.unmatched_discovered_issue_ceiling,
            "coverage_percent": report.coverage_percent,
            "largest_volumes": [
                {
                    "volume_id": row.volume_id,
                    "name": row.name,
                    "publisher": row.publisher,
                    "count_of_issues": row.count_of_issues,
                }
                for row in report.largest_volumes
            ],
            "top_publishers": [
                {
                    "publisher": row.publisher,
                    "volume_count": row.volume_count,
                    "total_issues": row.total_issues,
                }
                for row in report.top_publishers
            ],
        }
        print(json.dumps(payload, separators=(",", ":")))
    else:
        print(format_report(report, top_volumes=args.top_volumes, top_publishers=args.top_publishers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
