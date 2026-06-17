"""P97 — Generate queue repair plan from discovered-not-queued audit (dry-run planning)."""

from __future__ import annotations

import argparse
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_queue_repair_service import (  # noqa: E402
    build_queue_repair_plan,
    default_plan_path,
    save_queue_repair_plan,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate P97 queue repair plan JSON")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--output", type=str, default=None, help="Override plan JSON path")
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        plan = build_queue_repair_plan(session)

    out_path = save_queue_repair_plan(
        plan,
        path=__import__("pathlib").Path(args.output) if args.output else None,
    )
    counts: dict[str, int] = {}
    for row in plan:
        counts[row.recommended_action] = counts.get(row.recommended_action, 0) + 1

    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Wrote {len(plan)} rows to {out_path}")
    _log(f"Default path: {default_plan_path()}")
    _log("Action counts:")
    for action, n in sorted(counts.items()):
        _log(f"  {action}: {n}")
    if args.output is None:
        _log("")
        _log("Review the plan before: python scripts/p97_apply_queue_repair_plan.py --apply ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
