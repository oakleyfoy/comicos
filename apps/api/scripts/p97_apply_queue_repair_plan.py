"""P97 — Apply queue repair plan (dry-run default; --apply required to mutate)."""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_queue_repair_service import (  # noqa: E402
    apply_queue_repair_plan,
    default_plan_path,
    load_queue_repair_plan,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply P97 queue repair plan")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--plan", type=str, default=None, help="Plan JSON path")
    parser.add_argument("--apply", action="store_true", help="Write queue rows (default: dry-run)")
    parser.add_argument("--allow-requeue-failed", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan_path = __import__("pathlib").Path(args.plan) if args.plan else default_plan_path()
    plan = load_queue_repair_plan(plan_path)
    if not plan:
        _log(f"No plan rows at {plan_path}")
        return 2

    dry_run = not args.apply
    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        result = apply_queue_repair_plan(
            session,
            plan,
            dry_run=dry_run,
            allow_requeue_failed=args.allow_requeue_failed,
        )

    payload = {
        "database": describe_database_url(database_url),
        "plan_path": str(plan_path),
        **result.as_dict(),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _log(f"(database: {describe_database_url(database_url)})")
        _log(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
        _log(f"Plan: {plan_path}")
        _log(f"Considered: {result.considered}")
        _log(f"Would add / added: {result.would_add if dry_run else result.added}")
        if not dry_run:
            _log(f"Updated: {result.updated}")
        _log(f"Skipped: {result.skipped}")
        if dry_run:
            _log("")
            _log("Dry-run only — pass --apply after reviewing the repair plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
