"""P98-18G — Collector-value gap report for final shell expansion (read-only)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_collector_value_gap_service import (  # noqa: E402
    GROUP_A,
    GROUP_B,
    GROUP_C,
    GROUP_D,
    build_collector_value_gap_report,
    save_collector_value_outputs,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 collector-value shell gap report")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top", type=int, default=100)
    parser.add_argument("--include-non-useful", action="store_true")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        report = build_collector_value_gap_report(
            session,
            top_n=args.top,
            useful_only=not args.include_non_useful,
        )

    paths = save_collector_value_outputs(report)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Report: {paths[0]}")
    _log(f"Top volumes: {paths[1]}")
    _log(f"Groups: {paths[2]}")
    _log("")
    _log(f"Shells: {report.current_shells:,} / {report.discoverable_issues:,} ({report.coverage_percent}%)")
    _log(f"Useful missing shells: {report.useful_missing_shells:,}")
    _log(f"Projected coverage (all useful): {report.projected_coverage_all_useful}%")
    _log("")
    _log("TOP 20 COLLECTOR GAP VOLUMES")
    for row in report.top_opportunities[:20]:
        _log(
            f"  {row.publisher[:16]:<16} {row.volume[:36]:<36} "
            f"score={row.collector_value_score:>5.0f} missing={row.missing_shells:>4} "
            f"{row.execution_group} — {row.reason[:60]}"
        )
    _log("")
    for label, key in (
        ("GROUP_A (highest)", GROUP_A),
        ("GROUP_B (high)", GROUP_B),
        ("GROUP_C (general)", GROUP_C),
        ("GROUP_D (archival)", GROUP_D),
    ):
        rows = report.expansion_groups.get(key, [])
        shells = sum(int(r.get("missing_shells") or 0) for r in rows)
        _log(f"{label}: {len(rows)} volumes, {shells:,} missing shells")
    _log("")
    if len(report.scenarios) >= 3:
        for title, sc in zip(
            ("IF ONLY 5,000 SHELLS", "IF ONLY 10,000 SHELLS", "ALL USEFUL REMAINING"),
            report.scenarios,
        ):
            _log(title)
            _log(f"  Allocate: {sc.shells_allocated:,} shells across {sc.volume_count} volumes")
            _log(f"  Coverage after: {sc.coverage_percent_after}%")
            if sc.top_volumes:
                v0 = sc.top_volumes[0]
                _log(f"  First pick: {v0.get('volume')} ({v0.get('publisher')}) score={v0.get('collector_value_score')}")
            _log("")
    _log(report.recommendation)
    return 0


if __name__ == "__main__":
    sys.exit(main())
