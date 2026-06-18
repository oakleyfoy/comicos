"""P98-18E — Execute controlled long-tail issue shell expansion."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_shell_expansion_executor_service import (  # noqa: E402
    build_shell_expansion_plan,
    default_progress_path,
    execute_shell_expansion_plan,
    load_planner_volume_rows,
    save_shell_expansion_progress,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P98 controlled shell expansion executor")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--apply", action="store_true", help="Write issue shells (default: dry-run)")
    parser.add_argument("--max-shells", type=int, default=None)
    parser.add_argument("--tier", type=int, default=None, choices=(1, 2, 3, 4))
    parser.add_argument("--include-tier4", action="store_true")
    parser.add_argument("--commit-every", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dry_run = not args.apply
    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    volume_rows = load_planner_volume_rows(include_tier4=args.include_tier4)

    with Session(engine) as session:
        plan = build_shell_expansion_plan(
            session,
            volume_rows=volume_rows,
            max_shells=args.max_shells,
            tier=args.tier,
            include_tier4=args.include_tier4,
            dry_run=dry_run,
        )
        result = execute_shell_expansion_plan(
            session,
            plan,
            dry_run=dry_run,
            commit_every=args.commit_every,
        )

    if not dry_run and result.stats.issues_created > 0:
        save_shell_expansion_progress(
            start_shell_count=result.start_shell_count,
            current_shell_count=result.end_shell_count,
            global_discoverable=result.global_discoverable,
            shells_added_this_run=result.stats.issues_created,
            extra={
                "volumes_expanded": result.stats.volumes_expanded,
                "max_shells": args.max_shells,
                "tier_filter": args.tier,
                "include_tier4": args.include_tier4,
            },
        )
    elif dry_run:
        save_shell_expansion_progress(
            path=default_progress_path(),
            start_shell_count=result.start_shell_count,
            current_shell_count=result.start_shell_count,
            global_discoverable=result.global_discoverable,
            shells_added_this_run=0,
            extra={"last_dry_run_shells_to_create": plan.shells_to_create},
        )

    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
        return 0

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
    _log(f"Progress file: {default_progress_path()}")
    _log("")
    _log(f"Volumes Selected: {plan.volumes_selected}")
    _log(f"Shells To Create: {plan.shells_to_create:,}")
    _log("")
    _log("Publishers:")
    for pub, count in sorted(plan.shells_by_publisher.items(), key=lambda x: -x[1])[:25]:
        _log(f"  {pub[:36]:<36} {count:>8,}")
    _log("")
    if dry_run:
        _log("Dry-run only — pass --apply to create shells.")
    else:
        _log(f"Shells added this run: {result.stats.issues_created:,}")
        _log(f"Coverage: {result.coverage_percent}% (was {_coverage_before(result)}%)")
        _log("")
        _log("Publisher results:")
        for row in result.publisher_reports[:20]:
            _log(
                f"  {row.publisher[:32]:<32} volumes={row.volumes_expanded:>4} "
                f"shells={row.shells_added:>6,} gain=+{row.coverage_gain_percent}%"
            )
    return 0


def _coverage_before(result) -> str:
    return str(
        round(
            result.start_shell_count / result.global_discoverable * 100.0, 2
        )
        if result.global_discoverable
        else 0.0
    )


if __name__ == "__main__":
    sys.exit(main())
