"""P98 — Long-tail issue shell expansion planner (read-only)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_long_tail_shell_planner_service import (  # noqa: E402
    build_long_tail_shell_planner_report,
    save_planner_outputs,
    tier_number_from_label,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _print_scenario(title: str, scenario) -> None:
    _log(title)
    _log(f"  Expected shell gain: {scenario.expected_shell_gain:,}")
    _log(f"  Expected coverage gain: +{scenario.expected_coverage_gain_percent}%")
    _log("  Top publishers:")
    for row in scenario.publishers[:10]:
        _log(f"    {row['publisher'][:40]:<40} +{row['expected_shell_gain']:,} shells")
    _log("")


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 long-tail shell expansion planner")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top-publishers", type=int, default=100)
    parser.add_argument("--top-volumes", type=int, default=250)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        report = build_long_tail_shell_planner_report(
            session,
            top_publishers=args.top_publishers,
            top_volumes=args.top_volumes,
        )

    paths = save_planner_outputs(report)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Planner JSON: {paths[0]}")
    _log(f"Top publishers JSON: {paths[1]}")
    _log(f"Top volumes JSON (strategy, no tier 4): {paths[2]}")
    _log(f"Top volumes tier 4 JSON: {paths[3]}")
    _log("")
    _log("GLOBAL")
    _log(f"  Discoverable: {report.global_discoverable_issues:,}")
    _log(f"  Shells:       {report.global_current_shells:,}")
    _log(f"  Missing:      {report.global_missing_shells:,}")
    _log(f"  Coverage:     {report.global_coverage_percent}%")
    _log("")

    with_missing = [p for p in report.publishers if p.missing_shells > 0]
    total_missing = sum(p.missing_shells for p in with_missing)
    _log(f"Publishers with missing shells: {len(with_missing)} (sum={total_missing:,})")
    _log("")
    _log("TOP 15 EXPANSION PUBLISHERS")
    for row in report.top_expansion_publishers[:15]:
        _log(
            f"  {row.publisher[:36]:<36} missing={row.missing_shells:>6,} "
            f"score={row.expansion_score:>10,.0f} tier={row.priority_tier} pri={row.recommended_priority}"
        )
    _log("")
    _log("TOP 15 EXPANSION VOLUMES (strategy)")
    for row in report.top_expansion_volumes[:15]:
        _log(
            f"  {row.volume_name[:40]:<40} ({row.publisher[:20]}) "
            f"tier={tier_number_from_label(row.priority_tier)} pri={row.recommended_priority} "
            f"missing={row.missing_shells:>5} score={row.expansion_score:,.0f}"
        )
    _log("")

    if len(report.scenarios) >= 3:
        _print_scenario("IF WE BUILD THE NEXT 10,000 SHELLS", report.scenarios[0])
        _print_scenario("IF WE BUILD THE NEXT 25,000 SHELLS", report.scenarios[1])
        _print_scenario("IF WE BUILD THE NEXT 50,000 SHELLS", report.scenarios[2])

    _log(report.final_recommendation)
    return 0


if __name__ == "__main__":
    sys.exit(main())
