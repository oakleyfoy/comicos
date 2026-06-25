"""P101-B — GCD / ComicVine / ComicOS coverage comparison (read-only).

Usage:
  cd apps/api
  python scripts/p101_gcd_coverage_comparison.py --database-url $env:DATABASE_URL
  python scripts/p101_gcd_coverage_comparison.py --gcd-db data/p101/gcd.sqlite --json --output data/p101/gcd_coverage_comparison.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.gcd_barcode_import_service import gcd_engine_from  # noqa: E402
from app.services.p101_gcd_coverage_comparison_service import (  # noqa: E402
    P101B_YEARS,
    P101B_YEAR_MAX,
    P101B_YEAR_MIN,
    build_p101_gcd_coverage_report,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_report(payload: dict) -> None:
    totals = payload["totals"]
    print("=" * 72)
    print("P101-B GCD COVERAGE COMPARISON (read-only)")
    print("=" * 72)
    print(f"Database: {payload.get('database', 'unknown')}")
    print(f"GCD DB:   {payload.get('gcd_db') or '(not loaded)'}")
    print(f"Years:    {P101B_YEAR_MIN}–{P101B_YEAR_MAX} (breakdown)")
    print("")
    print("Totals (all years in source unless noted):")
    print(f"  ComicOS catalog issues     {_fmt(int(totals['comicos_issues']))}")
    print(f"  GCD issues                 {_fmt(int(totals['gcd_issues']))}")
    print(f"  ComicVine issues (vol sum) {_fmt(int(totals['comicvine_issues']))}")
    print("")
    print("Overlap / gaps (modern GCD keys vs catalog; CV volume gaps):")
    print(f"  Missing from ComicOS, in GCD        {_fmt(int(totals['missing_from_comicos_in_gcd']))}")
    print(f"  Missing from ComicOS, in ComicVine  {_fmt(int(totals['missing_from_comicos_in_comicvine']))}")
    print(f"  Present in GCD and ComicVine        {_fmt(int(totals['present_in_gcd_and_comicvine']))}")
    print(f"  Present only in GCD                 {_fmt(int(totals['present_only_in_gcd']))}")
    print(f"  Present only in ComicVine           {_fmt(int(totals['present_only_in_comicvine']))}")
    print(f"  CV volume gap issues (all years)    {_fmt(int(payload.get('comicvine_volume_gap_issues') or 0))}")
    print("")
    print(f"{'Year':<6} {'ComicOS':>10} {'GCD':>10} {'ComicVine':>10} {'Miss+GCD':>10} {'Miss+CV':>10} {'G&CV':>8} {'G only':>8} {'CV only':>8}")
    print("-" * 92)
    by_year = payload.get("by_year") or {}
    for year in P101B_YEARS:
        row = by_year.get(str(year), {})
        print(
            f"{year:<6} "
            f"{_fmt(int(row.get('comicos_issues', 0))):>10} "
            f"{_fmt(int(row.get('gcd_issues', 0))):>10} "
            f"{_fmt(int(row.get('comicvine_issues', 0))):>10} "
            f"{_fmt(int(row.get('missing_from_comicos_in_gcd', 0))):>10} "
            f"{_fmt(int(row.get('missing_from_comicos_in_comicvine', 0))):>10} "
            f"{_fmt(int(row.get('present_in_gcd_and_comicvine', 0))):>8} "
            f"{_fmt(int(row.get('present_only_in_gcd', 0))):>8} "
            f"{_fmt(int(row.get('present_only_in_comicvine', 0))):>8}"
        )
    print("")
    for note in payload.get("notes") or []:
        print(f"NOTE: {note}")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="P101-B GCD vs ComicVine vs ComicOS coverage")
    parser.add_argument("--database-url", default=None, help="ComicOS Postgres URL (default: env DATABASE_URL)")
    parser.add_argument("--gcd-db", default=None, help="GCD SQLite path (default: data/p101/gcd.sqlite if exists)")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument("--output", default=None, help="Write JSON report to this path")
    args = parser.parse_args()

    db_url = resolve_p97_database_url(args.database_url)
    db_label = describe_database_url(db_url)

    gcd_path: Path | None = None
    if args.gcd_db:
        gcd_path = Path(args.gcd_db)
    else:
        default = Path("data/p101/gcd.sqlite")
        if default.exists():
            gcd_path = default

    gcd_engine = None
    gcd_db_label: str | None = None
    if gcd_path is not None:
        if not gcd_path.exists():
            print(f"GCD database not found: {gcd_path}", file=sys.stderr)
            return 2
        gcd_engine = gcd_engine_from(str(gcd_path))
        gcd_db_label = str(gcd_path)

    engine = get_p97_engine(db_url)
    with Session(engine) as session:
        report = build_p101_gcd_coverage_report(session, gcd=gcd_engine, gcd_db=gcd_db_label)

    payload = report.to_json()
    payload["database"] = db_label

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_report(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
