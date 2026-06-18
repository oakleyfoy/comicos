"""P99-02 — Pending P97 queue drain plan (read-only)."""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p99_pending_queue_drain_service import (  # noqa: E402
    GROUP_1_MAJOR_CORE,
    GROUP_2_LEGACY_US,
    GROUP_4_FOREIGN_OR_LOW_PRIORITY,
    build_pending_queue_drain_plan,
    save_pending_queue_drain_outputs,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P99 pending queue drain plan")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top", type=int, default=250)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        plan = build_pending_queue_drain_plan(session, top_n=args.top)

    paths = save_pending_queue_drain_outputs(plan)

    if args.json:
        print(json.dumps(plan.as_dict(), indent=2))
        return 0

    ra = plan.report_answers
    _log(f"(database: {describe_database_url(database_url)})")
    _log(f"Plan: {paths[0]}")
    _log(f"Top volumes: {paths[1]}")
    _log(f"Batches: {paths[2]}")
    _log("")
    _log("SUMMARY")
    _log(f"  Pending queue rows: {ra['pending_queue_row_count']:,}")
    _log(f"  Shells without catalog (pending vols): {ra['pending_shells_without_catalog_link']:,}")
    _log(f"  Missing issues (queue field): {ra['pending_missing_issues_queued']:,}")
    _log("")
    _log("PENDING BY DRAIN GROUP")
    for row in plan.group_counts:
        if row["pending_rows"] <= 0:
            continue
        _log(
            f"  {row['group']:<32} rows={row['pending_rows']:>5,} "
            f"shells={row['shells_without_catalog']:>7,}"
        )
    _log("")
    _log("REPORT ANSWERS")
    _log(f"  Major/core pending rows: {ra['major_core_pending_rows']:,}")
    _log(f"  Legacy US pending rows: {ra['legacy_us_pending_rows']:,}")
    _log(f"  Foreign/low pending rows: {ra['foreign_low_priority_pending_rows']:,}")
    _log(f"  Safest first batch: {ra['safest_first_import_batch']}")
    _log(
        f"  Batch 1 scope: {ra['safest_first_batch_volumes']} volumes, "
        f"shell gap {ra['safest_first_batch_shell_gap']:,}, "
        f"est. catalog gain {ra['safest_first_batch_expected_catalog_gain']:,}"
    )
    _log("")
    _log("TOP 15 PENDING VOLUMES (drain rank)")
    for row in plan.top_volumes[:15]:
        _log(
            f"  #{row.rank:<3} score={row.drain_score:>6} {row.drain_group[:12]:<12} "
            f"{row.publisher or '':<16} {row.volume_name[:32]:<32} "
            f"shells={row.shells_without_catalog:>4} missing={row.missing_issue_count:>4}"
        )
    _log("")
    _log("BATCH SCENARIOS")
    for batch in plan.batches:
        _log(
            f"  {batch.batch_id}: {batch.label} — "
            f"{batch.volume_count} vols, shell gap {batch.shells_affected:,}, "
            f"est. gain {batch.expected_catalog_gain:,}"
        )
    _log("")
    _log(ra.get("explain_39826_pending", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
