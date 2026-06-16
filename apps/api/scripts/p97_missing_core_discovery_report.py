"""Report core run presence in comicvine_volume_universe (publisher-aware).

Usage:
  python scripts/p97_missing_core_discovery_report.py
  python scripts/p97_missing_core_discovery_report.py --json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_targeted_core_discovery import (  # noqa: E402
    build_core_discovery_status,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def format_report(rows, summary) -> str:
    lines = ["CORE DISCOVERY STATUS", ""]
    for row in rows:
        lines.append(row.report_label)
        lines.append(f"  Publisher: {row.expected_publisher}")
        lines.append(f"  Discovered: {'YES' if row.discovered else 'NO'}")
        if row.discovered:
            lines.append(f"  Publisher Match: {'YES' if row.publisher_match else 'NO'}")
            if row.volume_name:
                lines.append(f"  Volume: {row.volume_name} (id={row.volume_id})")
        lines.append("")

    lines.extend(
        [
            "SUMMARY",
            f"  Core Runs Total: {summary.core_runs_total}",
            f"  Core Runs Discovered: {summary.core_runs_discovered}",
            f"  Core Runs Missing: {summary.core_runs_missing}",
            f"  Discovery Coverage %: {summary.discovery_coverage_percent:.2f}",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 missing core discovery report")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine) as session:
        rows, summary = build_core_discovery_status(session)

    if args.json:
        print(
            json.dumps(
                {
                    "rows": [asdict(r) for r in rows],
                    "summary": asdict(summary),
                },
                indent=2,
            )
        )
    else:
        print(format_report(rows, summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
