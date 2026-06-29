"""Mark stale P104 hydration runs failed after kill/KeyboardInterrupt (does not alter complete assets)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p104_cover_hydration_service import (  # noqa: E402
    INTERRUPT_REASON_STALE_RUNNING,
    mark_stale_p104_hydration_runs_interrupted,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_OUT = Path("data/p104/mark_stale_runs.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mark running P104 hydration runs as failed/interrupted (e.g. after KeyboardInterrupt). "
            "Complete asset rows are left unchanged; in-flight downloading rows reset to pending."
        )
    )
    parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="Single run to close (must still be status=running). Omit to close all running runs.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write DB")
    parser.add_argument(
        "--no-reset-downloading",
        action="store_true",
        help="Do not reset downloading assets to pending",
    )
    parser.add_argument(
        "--reason",
        default=INTERRUPT_REASON_STALE_RUNNING,
        help="Stored on reset downloading assets and in run log note when present",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine, expire_on_commit=False) as session:
        report = mark_stale_p104_hydration_runs_interrupted(
            session,
            run_id=args.run_id,
            dry_run=args.dry_run,
            reset_downloading=not args.no_reset_downloading,
            reason=args.reason,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    if report.get("marked_count", 0) == 0 and args.run_id is not None:
        print(
            f"No change: run {args.run_id} is not an open running hydration run.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
