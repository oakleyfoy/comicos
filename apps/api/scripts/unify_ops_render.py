"""Apply catalog unification ops on the database in DATABASE_URL (e.g. Render).

Steps: pre-teardown migrations (if needed), Phase C, optional wipe, Phase D teardown.

Usage (PowerShell, from apps/api):
  $env:DATABASE_URL = '<your-render-postgres-url>'
  python scripts/unify_ops_render.py --dry-run
  python scripts/unify_ops_render.py --wipe
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("Set DATABASE_URL to your Render Postgres URL first.")

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Phase C + wipe dry-run only")
    parser.add_argument("--wipe", action="store_true", help="Run collection wipe (after Phase C)")
    parser.add_argument("--email", default=None, help="Limit wipe/backfill to one user")
    args = parser.parse_args()

    py = sys.executable
    _run([py, "-m", "alembic", "upgrade", "20260626_0100"])
    c_cmd = [py, "scripts/unify_run_phase_c.py"]
    if args.email:
        c_cmd.extend(["--email", args.email])
    if args.dry_run:
        c_cmd.append("--dry-run")
    _run(c_cmd)
    if args.wipe:
        w_cmd = [py, "scripts/unify_wipe_test_collection.py"]
        if args.email:
            w_cmd.extend(["--email", args.email])
        if args.dry_run:
            w_cmd.append("--dry-run")
        _run(w_cmd)
    if not args.dry_run:
        _run([py, "-m", "alembic", "upgrade", "head"])
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
