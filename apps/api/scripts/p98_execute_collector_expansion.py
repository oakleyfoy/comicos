"""P98-18H — Execute collector-value ranked issue shell expansion."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_collector_value_expansion_executor_service import (  # noqa: E402
    build_collector_expansion_plan,
    default_progress_path,
    execute_collector_expansion_plan,
    format_group_labels,
    load_baseline_useful_gap,
    parse_group_spec,
    save_collector_expansion_progress,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 collector-value shell expansion executor")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--apply", action="store_true", help="Write issue shells (default: dry-run)")
    parser.add_argument(
        "--group",
        type=str,
        default="A,B",
        help="Expansion groups: A, B, C, D (comma-separated). Default: A,B",
    )
    parser.add_argument(
        "--collector-ranked",
        action="store_true",
        help="Sort globally by collector score, missing shells, publisher priority",
    )
    parser.add_argument("--max-shells", type=int, default=None)
    parser.add_argument("--commit-every", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dry_run = not args.apply
    try:
        group_keys = parse_group_spec(args.group)
    except ValueError as exc:
        _log(str(exc))
        return 2

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    baseline_useful = load_baseline_useful_gap()

    with Session(engine) as session:
        plan = build_collector_expansion_plan(
            session,
            group_keys=group_keys,
            max_shells=args.max_shells,
            collector_ranked=args.collector_ranked,
            dry_run=dry_run,
        )
        result = execute_collector_expansion_plan(
            session,
            plan,
            dry_run=dry_run,
            commit_every=args.commit_every,
            baseline_useful_gap=baseline_useful,
        )

    group_label = format_group_labels(group_keys)
    progress_extra = {
        "selected_groups": group_label,
        "collector_ranked": args.collector_ranked,
        "max_shells": args.max_shells,
        "dry_run": dry_run,
    }
    if dry_run:
        save_collector_expansion_progress(
            start_shell_count=result.start_shell_count,
            current_shell_count=result.start_shell_count,
            global_discoverable=result.global_discoverable,
            collector_shells_added=0,
            remaining_useful_gap=baseline_useful,
            extra={**progress_extra, "planned_shells": plan.shells_to_create},
        )
    elif result.stats.issues_created > 0:
        save_collector_expansion_progress(
            start_shell_count=result.start_shell_count,
            current_shell_count=result.end_shell_count,
            global_discoverable=result.global_discoverable,
            collector_shells_added=result.stats.issues_created,
            remaining_useful_gap=result.remaining_useful_gap,
            extra=progress_extra,
        )

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    _log(f"Progress file: {default_progress_path()}")
    _log("")
    _log(f"Selected Groups: {group_label}")
    _log(f"Volumes: {plan.volumes_selected}")
    _log(f"Shells: {plan.shells_to_create:,}")
    _log(f"Projected Coverage Gain: +{plan.projected_coverage_gain_percent}%")
    if args.collector_ranked:
        _log("Ordering: collector-ranked")
    _log("")
    for row in result.volume_results:
        _log(
            f"{row.volume}\n"
            f"{row.publisher}\n"
            f"Score {row.collector_value_score:.0f}\n"
            f"Added {row.shells_added}\n"
            f"Coverage Gain +{row.coverage_gain_percent}%\n"
        )
    if dry_run:
        _log("Dry-run only — pass --apply to create shells.")
    else:
        _log(f"Shells added this run: {result.stats.issues_created:,}")
        _log(
            f"Coverage: {result.coverage_percent}% "
            f"(+{result.coverage_gain_percent}% from {result.start_shell_count:,})"
        )
        if result.remaining_useful_gap is not None:
            _log(f"Remaining useful gap: {result.remaining_useful_gap:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
