"""Production cron entry: P86 weekly release lifecycle (Wed 10pm Central)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="P86 weekly release lifecycle automation")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify DATABASE_URL and owner lookup; print plan; do not capture.",
    )
    args = parser.parse_args()

    if not os.environ.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1

    from app.services.release_lifecycle_cron import run_release_lifecycle_weekly_cron

    result = run_release_lifecycle_weekly_cron(dry_run=args.dry_run)
    if result.message:
        print(result.message, flush=True)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
