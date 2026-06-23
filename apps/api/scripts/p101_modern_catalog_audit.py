"""P101 Modern Catalog Acquisition — audit-only coverage report (2009–2026 focus publishers).

Read-only: does not import issues, covers, or inventory.

Usage:
  cd apps/api
  python scripts/p101_modern_catalog_audit.py --database-url "$DATABASE_URL"
  python scripts/p101_modern_catalog_audit.py --json --output data/p101/modern_catalog_audit.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p101_modern_catalog_audit_service import (  # noqa: E402
    P101_YEAR_MAX,
    P101_YEAR_MIN,
    audit_report_to_json,
    build_modern_catalog_audit_report,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_report(payload: dict) -> None:
    print("P101 MODERN CATALOG AUDIT (read-only)")
    print(f"Years: {P101_YEAR_MIN}–{P101_YEAR_MAX}")
    print(f"Database: {payload.get('database', 'unknown')}")
    print(f"catalog_issue_total={_fmt(int(payload['catalog_issue_total']))}")
    print(f"universe_volumes_total={_fmt(int(payload['universe_volumes_total']))}")
    print(f"universe_volumes_modern_focus={_fmt(int(payload['universe_volumes_modern_focus']))}")
    totals = payload.get("modern_focus_totals") or {}
    print(
        "modern_focus_totals: "
        f"existing(issue-year)={_fmt(int(totals.get('existing_issues_issue_year', 0)))} "
        f"discovered(volume-start-year)={_fmt(int(totals.get('discovered_issues_volume_start_year', 0)))} "
        f"gap={_fmt(int(totals.get('remaining_gap_volume_scope', 0)))} "
        f"queue_candidate_volumes={_fmt(int(totals.get('queue_candidate_volumes', 0)))}"
    )
    print(
        "all_publishers_by_issue_year: "
        f"2009-2026={_fmt(int(totals.get('all_publishers_issue_years_2009_2026', 0)))} "
        f"2010-2026={_fmt(int(totals.get('all_publishers_issue_years_2010_2026', 0)))} "
        f"2008={_fmt(int(totals.get('all_publishers_issue_year_2008', 0)))} "
        f"Unknown={_fmt(int(totals.get('all_publishers_issue_year_unknown', 0)))}"
    )
    print("")
    print("catalog_issue year totals (all publishers, top buckets):")
    year_totals = payload.get("year_totals_all_publishers") or {}
    for key, count in list(year_totals.items())[:20]:
        print(f"  {key}: {_fmt(int(count))}")
    if len(year_totals) > 20:
        print(f"  ... ({len(year_totals) - 20} more year buckets)")
    print("")
    print(f"{'Year':<8} {'Publisher':<12} {'Existing':>10} {'Discovered':>12} {'Imported':>10} {'Gap':>10}")
    print("-" * 66)
    for row in payload.get("rows") or []:
        year = row["year"]
        print(
            f"{str(year):<8} {row['publisher']:<12} "
            f"{_fmt(int(row['existing_issues'])):>10} "
            f"{_fmt(int(row['discovered_issues'])):>12} "
            f"{_fmt(int(row['imported_issues'])):>10} "
            f"{_fmt(int(row['remaining_gap'])):>10}"
        )
    print("")
    for note in payload.get("notes") or []:
        print(f"NOTE: {note}")


def main() -> int:
    parser = argparse.ArgumentParser(description="P101 modern catalog audit (2009+, audit-only)")
    parser.add_argument("--database-url", default=None, help="Production or local DATABASE_URL")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON report to path (default: data/p101/modern_catalog_audit.json when set implicitly)",
    )
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    try:
        with Session(engine) as session:
            report = build_modern_catalog_audit_report(session)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    payload = audit_report_to_json(report)
    payload["database"] = describe_database_url(database_url)

    out_path: Path | None = None
    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = API_ROOT / out_path
    elif not args.json:
        out_path = API_ROOT / "data" / "p101" / "modern_catalog_audit.json"

    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
