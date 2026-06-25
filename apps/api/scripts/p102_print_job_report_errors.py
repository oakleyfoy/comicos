"""Print full write-batch error lines from a catalog_import_job report JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import load_job_dashboard_dict  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--report", default=None, help="Path to exported job JSON")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.report:
        payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
    elif args.job_id is not None:
        with Session(get_engine()) as session:
            payload = load_job_dashboard_dict(session, args.job_id)
    else:
        print("Provide --job-id or --report", file=sys.stderr)
        return 2

    report = payload.get("report") or {}
    errors = report.get("errors") or []
    print(f"job_id={payload.get('job_id')} status={payload.get('status')} error_count={len(errors)}")
    for i, err in enumerate(errors[: args.limit], start=1):
        print(f"\n--- error {i} ---\n{err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
