"""P99-01 — Catalog acquisition / import gap report (read-only)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p99_catalog_acquisition_gap_service import (  # noqa: E402
    GAP_CATEGORIES,
    build_catalog_acquisition_gap_report,
    save_catalog_acquisition_gap_outputs,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def _fmt_category_row(category: str, count: int, pct: float, width: int = 28) -> str:
    label = f"{category}.".ljust(width, ".")
    return f"{label}{count:>8,}  ({pct:.2f}%)"


def main() -> int:
    parser = argparse.ArgumentParser(description="P99 catalog acquisition gap report")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sample-issues", type=int, default=500)
    parser.add_argument("--top-publishers", type=int, default=100)
    parser.add_argument("--top-volumes", type=int, default=250)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        report = build_catalog_acquisition_gap_report(
            session,
            issue_sample_limit=args.sample_issues,
            top_publishers=args.top_publishers,
            top_volumes=args.top_volumes,
        )

    paths = save_catalog_acquisition_gap_outputs(report)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
        return 0

    gs = report.global_summary
    fa = report.final_answers
    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Report: {paths[0]}")
    _log(f"Top publishers: {paths[1]}")
    _log(f"Top volumes: {paths[2]}")
    _log("")
    _log("GLOBAL")
    _log(f"  Issue shells:     {gs['issue_shells']:,}")
    _log(f"  Catalog (series-linked): {gs['catalog_issues_series_linked']:,}")
    _log(f"  Catalog (universe-linked): {gs['catalog_issues_universe_linked']:,}")
    _log(f"  Import gap (P98 headline): {gs['import_gap_p98_headline']:,}")
    _log(f"  Import gap (discovered shells): {gs['import_gap_universe_discovered']:,}")
    _log(f"  Shell-to-catalog: {gs['shell_to_catalog_coverage_percent']}%")
    _log("")
    _log("GAP BY CATEGORY")
    for row in report.gap_by_category:
        if row["issue_count"] <= 0 and row["category"] not in GAP_CATEGORIES[:3]:
            continue
        _log(_fmt_category_row(row["category"], row["issue_count"], row["percent"]))
    _log("")
    _log("FINAL ANSWERS")
    _log(f"  Already queued (pending+running): {fa['already_queued_pending_or_running']:,}")
    _log(f"  Waiting (pending):                {fa['waiting_pending']:,}")
    _log(f"  Waiting (running):                {fa['waiting_running']:,}")
    _log(f"  Failed import:                    {fa['failed_import']:,}")
    _log(f"  Not queued:                       {fa['not_queued']:,}")
    _log(f"  Require new acquisition logic:    {fa['require_new_acquisition_logic']:,}")
    _log("")
    _log("TOP 15 PUBLISHERS BY IMPORT GAP")
    for row in report.publishers[:15]:
        _log(
            f"  {row.publisher[:28]:<28} gap={row.import_gap:>6,} "
            f"shells={row.shells:>7,} catalog={row.catalog_issues:>7,} "
            f"cov={row.coverage_percent}%"
        )
    _log("")
    _log("TOP 15 VOLUMES BY GAP")
    for row in report.top_volumes[:15]:
        _log(
            f"  {row.publisher[:16]:<16} {row.volume[:32]:<32} "
            f"gap={row.gap:>4} queue={row.queue_status}"
        )
    _log("")
    _log("HIGH-VALUE GAP ISSUES (sample)")
    for row in report.high_value_gap_issues[:10]:
        _log(
            f"  {row.get('publisher', '')[:12]:<12} {row.get('volume', '')[:28]:<28} "
            f"#{row.get('issue_number')} {row.get('gap_reason')}"
        )
    _log("")
    _log(fa.get("fastest_path_summary", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
