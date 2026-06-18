"""P98 — Publisher match audit for core US series."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_publisher_match_audit_service import build_publisher_match_audit  # noqa: E402
from app.services.p98_publisher_match_repair_service import save_publisher_match_rule_analysis  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 publisher match audit")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-rule-analysis", action="store_true")
    args = parser.parse_args()

    if args.write_rule_analysis:
        path = save_publisher_match_rule_analysis()
        _log(f"Wrote rule analysis: {path}")

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        rows = build_publisher_match_audit(session)

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
    _log("P98 PUBLISHER MATCH AUDIT")
    _log("")
    _log(
        f"{'ID':>8}  {'Type':<24}  {'Missing':>7}  {'Expected':<18}  "
        f"{'Matched':<18}  Name"
    )
    for row in rows:
        _log(
            f"{row.volume_id:>8}  {row.publisher_match_type:<24}  {row.missing_issues:>7}  "
            f"{(row.expected_publisher or '')[:18]:<18}  "
            f"{(row.matched_publisher or '')[:18]:<18}  {row.volume_name[:40]}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
