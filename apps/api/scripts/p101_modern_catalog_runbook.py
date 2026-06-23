"""P101 Modern Catalog Acquisition — audit, queue preview/build, PowerShell runbook.

Catalog only (catalog_issue / catalog_image / catalog_upc). Does not touch inventory.

Usage (from apps/api):
  python scripts/p101_modern_catalog_runbook.py audit --database-url $env:DATABASE_URL
  python scripts/p101_modern_catalog_runbook.py queue-preview --database-url $env:DATABASE_URL
  python scripts/p101_modern_catalog_runbook.py queue-build --database-url $env:DATABASE_URL --apply
  python scripts/p101_modern_catalog_runbook.py plan --write-ps1
  python scripts/p101_modern_catalog_runbook.py plan --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p101_modern_catalog_acquisition_service import (  # noqa: E402
    P101_YEAR_MAX,
    P101_YEAR_MIN,
    build_p101_queue,
    build_p101_runbook_plan,
    preview_p101_queue,
    runbook_plan_to_json,
)
from app.services.p101_modern_catalog_audit_service import (  # noqa: E402
    audit_report_to_json,
    build_modern_catalog_audit_report,
)
from p97_db import (  # noqa: E402
    describe_database_url,
    explain_database_url_error,
    get_p97_engine,
    resolve_p97_database_url,
)


def _fmt(n: int) -> str:
    return f"{n:,}"


def _print_preview(preview) -> None:
    print(f"P101 QUEUE PREVIEW (dry-run) years={P101_YEAR_MIN}-{P101_YEAR_MAX}")
    print(f"universe_volumes_total={_fmt(preview.universe_volumes_total)}")
    print(f"modern_focus_volumes={_fmt(preview.modern_focus_volumes)}")
    print(f"gap_volumes={_fmt(preview.gap_volumes)}")
    print(f"missing_issues={_fmt(preview.missing_issues)}")
    print("by_publisher:")
    for label, stats in preview.by_publisher.items():
        print(f"  {label}: volumes={_fmt(stats['gap_volumes'])} missing_issues={_fmt(stats['missing_issues'])}")
    print("")
    print("top_gap_volumes:")
    for row in preview.top_gap_volumes[:25]:
        print(
            f"  vol={row.comicvine_volume_id} {row.publisher_label} ({row.start_year}) "
            f"missing={row.missing_issue_count}/{row.count_of_issues} {row.name[:60]!r}"
        )


def _print_build(result) -> None:
    mode = "DRY-RUN" if result.dry_run else "APPLIED"
    print(f"P101 QUEUE BUILD [{mode}]")
    _print_preview(result.preview)
    if not result.dry_run:
        print("")
        print(f"queue_rows_inserted={_fmt(result.build_inserted)}")
        print(f"queue_rows_updated={_fmt(result.build_updated)}")
        print(f"pending_queue_size(all)={_fmt(result.pending_queue_size)}")
    print(f"p101_pending_volumes={_fmt(result.p101_pending_volumes)}")
    print(f"p101_pending_missing_issues={_fmt(result.p101_pending_missing_issues)}")


def cmd_audit(session: Session, *, as_json: bool, database_label: str) -> int:
    report = build_modern_catalog_audit_report(session)
    payload = audit_report_to_json(report)
    payload["database"] = database_label
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    totals = payload.get("modern_focus_totals") or {}
    yt = payload.get("year_totals_all_publishers") or {}
    print("P101 MODERN CATALOG AUDIT (read-only)")
    print(f"Database: {database_label}")
    print(f"catalog_issue_total={_fmt(int(payload['catalog_issue_total']))}")
    print(f"universe_volumes_total={_fmt(int(payload['universe_volumes_total']))}")
    print(
        "all_publishers_by_issue_year: "
        f"2009-2026={_fmt(int(totals.get('all_publishers_issue_years_2009_2026', 0)))} "
        f"2010-2026={_fmt(int(totals.get('all_publishers_issue_years_2010_2026', 0)))} "
        f"Unknown={_fmt(int(totals.get('all_publishers_issue_year_unknown', 0)))}"
    )
    print(f"gap (universe scope): missing_issues={_fmt(int(totals.get('remaining_gap_volume_scope', 0)))}")
    if int(payload.get("universe_volumes_total") or 0) == 0:
        print("NOTE: Run p97_discover_comicvine_universe before queue-preview will show gaps.")
    return 0


def cmd_queue_preview(session: Session, *, top: int, as_json: bool) -> int:
    preview = preview_p101_queue(session, top=top)
    if as_json:
        print(
            json.dumps(
                {
                    "mode": "dry_run",
                    "preview": {
                        **preview.__dict__,
                        "top_gap_volumes": [row.__dict__ for row in preview.top_gap_volumes],
                    },
                },
                indent=2,
                default=str,
            )
        )
    else:
        _print_preview(preview)
    return 0


def cmd_queue_build(session: Session, *, apply: bool, refresh_complete: bool, top: int, as_json: bool) -> int:
    result = build_p101_queue(session, dry_run=not apply, refresh_complete=refresh_complete, preview_top=top)
    if as_json:
        print(
            json.dumps(
                {
                    "dry_run": result.dry_run,
                    "build_inserted": result.build_inserted,
                    "build_updated": result.build_updated,
                    "pending_queue_size": result.pending_queue_size,
                    "p101_pending_volumes": result.p101_pending_volumes,
                    "p101_pending_missing_issues": result.p101_pending_missing_issues,
                    "preview": {
                        **result.preview.__dict__,
                        "top_gap_volumes": [row.__dict__ for row in result.preview.top_gap_volumes],
                    },
                },
                indent=2,
                default=str,
            )
        )
    else:
        _print_build(result)
        if not apply:
            print("")
            print("To write queue rows: queue-build --apply")
    return 0


def cmd_plan(*, write_ps1: bool, as_json: bool) -> int:
    plan = build_p101_runbook_plan(api_root=str(API_ROOT))
    payload = runbook_plan_to_json(plan)
    out_dir = API_ROOT / "data" / "p101"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "modern_catalog_runbook.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if write_ps1:
        ps1_path = out_dir / "modern_catalog_runbook.ps1"
        ps1_path.write_text("\r\n".join(plan.powershell_commands) + "\r\n", encoding="utf-8")
        print(f"Wrote {ps1_path}", file=sys.stderr)
    print(f"Wrote {json_path}", file=sys.stderr)

    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        print("P101 MODERN CATALOG RUNBOOK (PowerShell)")
        print(f"Years: {P101_YEAR_MIN}-{P101_YEAR_MAX}")
        print("Prerequisites:")
        for line in plan.prerequisites:
            print(f"  - {line}")
        print("")
        print("Phases:")
        for phase in plan.phases:
            dry = "dry-run" if phase.get("dry_run") or phase.get("dry_run_first") else "live"
            print(f"  [{dry}] {phase['id']}: {phase['title']}")
        print("")
        print("Commands (also in data/p101/modern_catalog_runbook.ps1):")
        for line in plan.powershell_commands:
            print(line)
    return 0


def main() -> int:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--database-url",
        default=None,
        help="Postgres URL (optional if DATABASE_URL is in apps/api/.env)",
    )
    shared.add_argument("--json", action="store_true")

    parser = argparse.ArgumentParser(description="P101 modern catalog acquisition runbook")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("audit", parents=[shared], help="Same as p101_modern_catalog_audit.py")

    p_preview = sub.add_parser(
        "queue-preview",
        parents=[shared],
        help="Dry-run: modern gap volumes (no queue writes)",
    )
    p_preview.add_argument("--top", type=int, default=50)

    p_build = sub.add_parser(
        "queue-build",
        parents=[shared],
        help="Preview by default; pass --apply to run p97 queue build",
    )
    p_build.add_argument("--apply", action="store_true", help="Call p97_build_volume_issue_import_queue")
    p_build.add_argument("--refresh-complete", action="store_true")
    p_build.add_argument("--top", type=int, default=50)

    p_plan = sub.add_parser("plan", parents=[shared], help="Emit PowerShell import plan (dry-run steps first)")
    p_plan.add_argument("--write-ps1", action="store_true", help="Write data/p101/modern_catalog_runbook.ps1")

    args = parser.parse_args()

    if args.command == "plan":
        return cmd_plan(write_ps1=bool(args.write_ps1), as_json=bool(args.json))

    database_url = resolve_p97_database_url(args.database_url)
    url_error = explain_database_url_error(database_url)
    if url_error:
        print(f"ERROR: {url_error}", file=sys.stderr)
        return 2
    engine = get_p97_engine(database_url)
    db_label = describe_database_url(database_url)
    with Session(engine) as session:
        if args.command == "audit":
            return cmd_audit(session, as_json=bool(args.json), database_label=db_label)
        if args.command == "queue-preview":
            return cmd_queue_preview(session, top=int(args.top), as_json=bool(args.json))
        if args.command == "queue-build":
            return cmd_queue_build(
                session,
                apply=bool(args.apply),
                refresh_complete=bool(args.refresh_complete),
                top=int(args.top),
                as_json=bool(args.json),
            )
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
