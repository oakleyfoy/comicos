"""P104 cover hydration dry-run CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p104_cover_hydration_service import run_p104_dry_run  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_OUT = Path("data/p104/cover_hydration_dryrun.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="P104 cover hydration dry-run (survey + optional queue sync)")
    parser.add_argument("--pilot-limit", type=int, default=100, help="Simulate first N pending asset rows")
    parser.add_argument(
        "--sync-limit",
        type=int,
        default=0,
        help="Explicit queue-build: upsert up to N asset rows before pilot simulation (0 = survey only)",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine) as session:
        report = run_p104_dry_run(session, pilot_limit=args.pilot_limit, sync_limit=args.sync_limit)
        session.commit()
    payload = {"report": report.to_dict()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
