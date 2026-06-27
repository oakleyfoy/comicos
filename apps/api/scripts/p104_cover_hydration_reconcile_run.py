"""Reconcile P104 hydration run: fix stale asset status and run counters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p104_cover_hydration_service import reconcile_p104_hydration_run  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_OUT = Path("data/p104/reconcile_run.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="P104 reconcile hydration run status vs on-disk files")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write DB")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine, expire_on_commit=False) as session:
        report = reconcile_p104_hydration_run(session, args.run_id, dry_run=args.dry_run)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
