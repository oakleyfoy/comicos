"""P98 — Issue shell expansion planning report (read-only)."""

from __future__ import annotations

import argparse
import json

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_issue_shell_expansion_service import (  # noqa: E402
    build_expansion_report,
    default_queue_path,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 issue shell expansion report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--queue", type=str, default=None)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    from pathlib import Path

    queue_path = Path(args.queue) if args.queue else default_queue_path()

    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        report = build_expansion_report(session, queue_path=queue_path)

    if args.json:
        print(json.dumps({"database": describe_database_url(database_url), **report.as_dict()}))
        return

    print("P98 ISSUE SHELL EXPANSION")
    print(f"(database: {describe_database_url(database_url)})")
    print("")
    print("Volumes Expanded: (run p98_expand_issue_shells.py --apply to populate)")
    print(f"Issues (current):  {report.current_issues}")
    print(f"Variants (current): {report.current_variants}")
    print("")
    print("By Publisher (remaining BUILD_ISSUE_SHELLS volumes):")
    for pub in sorted(report.by_publisher_remaining.keys()):
        gain = report.by_publisher_projected_gain.get(pub, 0)
        print(f"  {pub}: {report.by_publisher_remaining[pub]} volumes, +{gain} issues projected")
    print("")
    print(f"Remaining BUILD_ISSUE_SHELLS: {report.remaining_build_shells_volumes}")
    print("")
    print("Projected Issue Count:")
    print(f"  Current:   {report.current_issues}")
    print(f"  Projected: {report.projected_issue_total}")
    print(f"  Gain:      {report.projected_gain}")


if __name__ == "__main__":
    main()
