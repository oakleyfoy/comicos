"""Export P103.5 exception backlog JSON/CSV from a dry-run or write report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from app.services.p1035_gcd_identity_exception_service import (  # noqa: E402
    format_p1035_exception_summary,
    load_exceptions_from_report_file,
    write_p1035_exception_backlog,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="P103.5 exception backlog export")
    parser.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Dry-run or write JSON report (must include exceptions payload from a current P103.5 run)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/p1035/exceptions"),
        help="Directory for ambiguous_matches.json/.csv and related files",
    )
    args = parser.parse_args()

    try:
        exceptions = load_exceptions_from_report_file(args.report)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    summary = write_p1035_exception_backlog(exceptions, args.out_dir)
    print(format_p1035_exception_summary(summary))
    print(f"Wrote exception files under: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
