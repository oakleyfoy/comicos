"""P98 — Major publisher gap coverage report (read-only planning).

Examples:
  python scripts/p98_major_publisher_gap_report.py --publisher Marvel --top 100
  python scripts/p98_major_publisher_gap_report.py --publisher "DC Comics" --top 100
  python scripts/p98_major_publisher_gap_report.py --json
  python scripts/p98_major_publisher_gap_report.py --csv data/p98/marvel_gap_report.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_skeleton_gap_service import (  # noqa: E402
    get_priority_gap_volumes,
    get_publisher_gap_summary,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _print_report(summary, rows) -> None:
    print(f"Publisher: {summary.publisher}")
    print("")
    print("Universe Volumes:")
    print(f"  Catalog Complete: {summary.catalog_complete}")
    print(f"  Catalog Partial:  {summary.catalog_partial}")
    print(f"  Shell Only:       {summary.shell_only}")
    print(f"  Volume Only:      {summary.volume_only}")
    if summary.unknown:
        print(f"  Unknown:          {summary.unknown}")
    print(f"  Total:            {summary.universe_volumes}")
    print("")
    print(f"Universe Issues:        {summary.universe_issues}")
    print(f"Catalog Linked Issues:  {summary.catalog_linked_issues}")
    print(f"Discovered Only Issues: {summary.discovered_only_issues}")
    print("")
    print(f"Coverage Percent:        {summary.coverage_percent}%")
    print(f"Shell Coverage Percent:  {summary.shell_coverage_percent}%")
    print(f"Volume Coverage Percent: {summary.volume_coverage_percent}%")
    print("")
    print("Top Missing Volumes:")
    print(
        f"  {'Volume':<40} {'CV ID':>8} {'Year':>6} {'Status':<17} "
        f"{'Univ':>6} {'Cat':>6} {'Miss':>6} {'Score':>8}"
    )
    for r in rows:
        print(
            f"  {r.volume_name[:40]:<40} {r.comicvine_volume_id:>8} "
            f"{(r.start_year or 0):>6} {r.status:<17} "
            f"{r.universe_issue_count:>6} {r.catalog_issue_count:>6} "
            f"{r.missing_issue_count:>6} {r.priority_score:>8}"
        )


def _write_csv(path: str, rows) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "publisher",
                "volume",
                "comicvine_volume_id",
                "start_year",
                "status",
                "universe_issue_count",
                "catalog_issue_count",
                "missing_issue_count",
                "recommended_action",
                "priority_score",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.publisher_name,
                    r.volume_name,
                    r.comicvine_volume_id,
                    r.start_year or "",
                    r.status,
                    r.universe_issue_count,
                    r.catalog_issue_count,
                    r.missing_issue_count,
                    r.recommended_action,
                    r.priority_score,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 major publisher gap report")
    parser.add_argument("--publisher", type=str, default=None)
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--csv", type=str, default=None)
    parser.add_argument("--database-url", type=str, default=None)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        summary = get_publisher_gap_summary(session, publisher=args.publisher)
        rows = get_priority_gap_volumes(session, publisher=args.publisher, top=args.top)

    if args.csv:
        _write_csv(args.csv, rows)

    if args.json:
        print(
            json.dumps(
                {
                    "database": describe_database_url(database_url),
                    "summary": summary.as_dict(),
                    "top_missing_volumes": [r.as_dict() for r in rows],
                }
            )
        )
        return

    print(f"(database: {describe_database_url(database_url)})")
    _print_report(summary, rows)
    if args.csv:
        print("")
        print(f"CSV written: {args.csv}")


if __name__ == "__main__":
    main()
