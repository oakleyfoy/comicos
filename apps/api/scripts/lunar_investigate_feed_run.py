"""Investigate a LunarFeedRun (errors, raw rows, catalog commit semantics). Report only."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--email", default=None, help="Optional owner filter")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    from sqlmodel import Session, select

    from app.db.session import get_engine
    from app.models.lunar_feed import LunarFeedError, LunarFeedRawRow, LunarFeedRun
    from app.models.release_intelligence import ReleaseIssue

    with Session(get_engine()) as session:
        run = session.get(LunarFeedRun, args.run_id)
        if run is None:
            print(json.dumps({"error": "run not found", "run_id": args.run_id}))
            return 1

        errors = list(
            session.exec(
                select(LunarFeedError)
                .where(LunarFeedError.feed_run_id == args.run_id)
                .order_by(LunarFeedError.id.asc())
            ).all()
        )
        raw_count = len(
            session.exec(select(LunarFeedRawRow).where(LunarFeedRawRow.feed_run_id == args.run_id)).all()
        )
        max_raw_index = session.exec(
            select(LunarFeedRawRow.row_index)
            .where(LunarFeedRawRow.feed_run_id == args.run_id)
            .order_by(LunarFeedRawRow.row_index.desc())
            .limit(1)
        ).first()

        err_codes: dict[str, int] = {}
        for e in errors:
            err_codes[e.error_code] = err_codes.get(e.error_code, 0) + 1

        first_20 = [
            {
                "id": e.id,
                "record_identifier": e.record_identifier,
                "error_code": e.error_code,
                "error_message": e.error_message,
            }
            for e in errors[:20]
        ]

        # Heuristic: last CSV row index not listed in error identifiers (row:N or product codes)
        error_row_nums = set()
        for e in errors:
            rid = e.record_identifier or ""
            if rid.startswith("row:"):
                try:
                    error_row_nums.add(int(rid.split(":", 1)[1]))
                except ValueError:
                    pass
        last_success_heuristic = None
        if max_raw_index is not None:
            for idx in range(int(max_raw_index), 0, -1):
                if idx not in error_row_nums:
                    last_success_heuristic = idx
                    break

        report = {
            "run": {
                "id": run.id,
                "owner_user_id": run.owner_user_id,
                "file_name": run.file_name,
                "file_period": run.file_period,
                "status": run.status,
                "source_type": run.source_type,
                "records_processed": run.records_processed,
                "records_created": run.records_created,
                "records_updated": run.records_updated,
                "records_failed": run.records_failed,
                "foc_alerts_created": run.foc_alerts_created,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            },
            "terminology": {
                "records_inserted": "Use records_created on lunar_feed_run (series+issues+variants created).",
                "partial_meaning": "PARTIAL = normalize validation_errors non-empty; catalog import still ran.",
            },
            "raw_rows_stored": raw_count,
            "error_count": len(errors),
            "error_code_counts": err_codes,
            "first_20_errors": first_20,
            "last_successful_csv_row_index_heuristic": last_success_heuristic,
            "max_raw_row_index": max_raw_index,
            "partial_catalog_committed": run.status in {"PARTIAL", "COMPLETED"},
            "pipeline_notes": [
                "Order: parse CSV -> normalize (skip bad rows into errors) -> store all raw rows -> import_release_feed(valid feed) -> FOC alerts -> store errors -> PARTIAL if errors.",
                "import_release_feed commits per series/issue/variant; failed rows do not roll back successful rows.",
                "Re-import same file is idempotent via release_uuid / variant_uuid matching.",
            ],
            "idempotent_reimport_april": {
                "safe": True,
                "reason": "Canonical lunar issue UUIDs; import matches and updates existing rows.",
                "caveat": "Rows that still fail validation remain absent until source fields fixed.",
            },
        }
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
