"""Compare and optionally apply collector-first P97 queue priority rebalance.

Usage:
  python scripts/p97_queue_rebalance_report.py
  python scripts/p97_queue_rebalance_report.py --apply
"""

from __future__ import annotations

import argparse
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_queue_rebalance_service import (  # noqa: E402
    apply_queue_rebalance,
    build_rebalance_comparison,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt_row(
    rank: int,
    name: str,
    publisher: str | None,
    score: float,
    *,
    missing: int | None = None,
    run_size: int | None = None,
    core: bool | None = None,
) -> str:
    pub = (publisher or "Unknown")[:22]
    extras = ""
    if missing is not None and run_size is not None and core is not None:
        flag = "YES" if core else "NO"
        extras = f" miss={missing:,} run={run_size:,} core={flag}"
    return f"  {rank:>3}. [{score:,.0f}] {name[:48]} ({pub}){extras}"


def _fmt_core(entry) -> list[str]:
    return [
        f"  {entry.name[:52]}",
        f"    Missing: {entry.missing_issue_count:,}  Run Size: {entry.run_size:,}  "
        f"Score: {entry.score:,.0f}",
    ]


def _fmt_coverage(entry) -> list[str]:
    pub = (entry.publisher or "Unknown")[:24]
    return [
        f"  {entry.name[:40]:<40} {pub:<24} "
        f"Missing: {entry.missing_issue_count:,}  Run: {entry.run_size:,}  "
        f"Score: {entry.score:,.0f}",
    ]


def format_comparison_report(report) -> str:
    lines = [
        "P97 QUEUE REBALANCE COMPARISON (core-run + coverage scoring)",
        "",
        f"Eligible queue rows (pending/running/failed): {report.eligible_row_count:,}",
        "",
        "CURRENT TOP 100 (by stored priority_score)",
        "",
    ]
    for entry in report.current_top_100:
        lines.append(
            _fmt_row(
                entry.rank,
                entry.name,
                entry.publisher,
                entry.priority_score,
                missing=entry.missing_issue_count,
                run_size=entry.run_size,
                core=entry.is_core_run,
            )
        )

    lines.extend(["", "REBALANCED TOP 100 (by new collector score)", ""])
    for entry in report.rebalanced_top_100:
        lines.append(
            _fmt_row(
                entry.rank,
                entry.name,
                entry.publisher,
                float(entry.rebalance_score or 0.0),
                missing=entry.missing_issue_count,
                run_size=entry.run_size,
                core=entry.is_core_run,
            )
        )

    lines.extend(["", "TOP CORE RUNS (rebalanced priority order)", ""])
    for entry in report.top_core_runs:
        lines.extend(_fmt_core(entry))

    lines.extend(["", "TOP COVERAGE OPPORTUNITIES (by missing issues)", ""])
    for entry in report.top_coverage_opportunities:
        lines.extend(_fmt_coverage(entry))

    lines.extend(
        [
            "",
            f"Coverage gain potential (top opportunities missing sum): {report.coverage_gain_potential:,}",
            "",
            "CORE RUNS BEFORE (stored priority order)",
            "",
        ]
    )
    for entry in report.core_runs_before:
        lines.extend(_fmt_core(entry))

    lines.extend(["", "CORE RUNS AFTER (rebalanced order)", ""])
    for entry in report.core_runs_after:
        lines.extend(_fmt_core(entry))

    lines.extend(["", "LARGEST COVERAGE MOVERS (by missing issues, moved up)", ""])
    for move in report.largest_coverage_movers:
        lines.append(f"  {move.name[:52]}")
        lines.append(
            f"    Missing: {move.missing_issue_count:,}  "
            f"Old Rank: {move.old_rank}  New Rank: {move.new_rank}"
        )

    lines.extend(["", "LARGEST MOVERS UP (old rank -> new rank)", ""])
    for move in report.largest_movers_up:
        lines.append(f"  {move.name[:52]}")
        lines.append(f"    Old Rank: {move.old_rank}  New Rank: {move.new_rank}")

    lines.extend(["", "LARGEST MOVERS DOWN (old rank -> new rank)", ""])
    for move in report.largest_movers_down:
        lines.append(f"  {move.name[:52]}")
        lines.append(f"    Old Rank: {move.old_rank}  New Rank: {move.new_rank}")

    lines.extend(["", "PUBLISHER DISTRIBUTION (current top 100)", ""])
    for pub, count in report.current_top_100_publisher_distribution.items():
        lines.append(f"  {pub[:40]:<40} {count}")

    lines.extend(["", "PUBLISHER DISTRIBUTION (rebalanced top 100)", ""])
    for pub, count in report.rebalanced_top_100_publisher_distribution.items():
        lines.append(f"  {pub[:40]:<40} {count}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 queue rebalance report")
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write updated priority_score values (pending/failed, non-manual)",
    )
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine) as session:
        report = build_rebalance_comparison(session)
        print(format_comparison_report(report))
        print("")
        apply_result = apply_queue_rebalance(session, dry_run=not args.apply)
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"Mode: {mode}")
        print(f"Rows considered for update: {apply_result.rows_considered:,}")
        print(
            f"Priority scores {'would change' if apply_result.dry_run else 'changed'}: "
            f"{apply_result.rows_updated:,}"
        )
        print(f"Manual tier rows skipped: {apply_result.rows_skipped_manual:,}")
        print(
            f"Queue row count before/after: {apply_result.row_count_before:,} / "
            f"{apply_result.row_count_after:,}"
        )
        if apply_result.row_count_before != apply_result.row_count_after:
            print("ERROR: queue row count changed", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
