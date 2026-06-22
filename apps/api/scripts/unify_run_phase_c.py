"""Run Phase C data steps (catalog links + grading catalog_issue_id).

Usage (from apps/api):
  python scripts/unify_run_phase_c.py --dry-run
  python scripts/unify_run_phase_c.py --email user@example.com
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C: backfill catalog links + grading ids.")
    parser.add_argument("--email", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    py = sys.executable
    common = []
    if args.email:
        common.extend(["--email", args.email])
    if args.dry_run:
        common.append("--dry-run")

    steps = [
        [py, "scripts/unify_backfill_catalog_issue.py", *common, "--provenance"],
        [py, "scripts/unify_backfill_grading_catalog.py", *common],
    ]
    reports = {}
    for cmd in steps:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            raise SystemExit(proc.returncode)
        try:
            reports[cmd[1]] = json.loads(proc.stdout)
        except json.JSONDecodeError:
            reports[cmd[1]] = {"raw": proc.stdout.strip()}

    print(json.dumps(reports, indent=2, default=str))


if __name__ == "__main__":
    main()
