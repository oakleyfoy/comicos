"""One-time / ranged LoCG calendar backfill into external_catalog tables."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--through-farthest-available", action="store_true")
    parser.add_argument("--max-detail-pages", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    args = parser.parse_args()

    if args.production and not os.environ.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required for --production", file=sys.stderr)
        return 1

    from app.services.external_catalog.sync_service import backfill_calendar

    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date) if args.end_date else None

    if args.dry_run:
        if end is None:
            print("error: --end-date required for --dry-run probe", file=sys.stderr)
            return 1
        summary = backfill_calendar(
            None,  # type: ignore[arg-type]
            start_date=start,
            end_date=end,
            dry_run=True,
            max_detail_pages_override=args.max_detail_pages,
            delay_seconds=args.delay_seconds,
        )
        print(json.dumps(summary, indent=2, default=str))
        return 0

    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        db_path = os.path.join(ROOT, ".locg_validation.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        _init_validation_sqlite_schema()

    from sqlmodel import Session

    from app.db.session import get_engine

    calendar_dates = None
    if end is not None:
        from datetime import timedelta

        calendar_dates = []
        cursor = start
        while cursor <= end:
            calendar_dates.append(cursor)
            cursor += timedelta(days=1)

    with Session(get_engine()) as session:
        summary = backfill_calendar(
            session,
            start_date=start,
            end_date=end,
            through_farthest_available=args.through_farthest_available,
            max_detail_pages=args.max_detail_pages,
            max_detail_pages_override=args.max_detail_pages,
            dry_run=False,
            resume=args.resume,
            refresh_existing=args.refresh_existing,
            delay_seconds=args.delay_seconds,
            calendar_dates=calendar_dates,
        )
        if end is not None and args.max_detail_pages <= 20:
            summary["validation"] = _summarize_stored_issues(session)
    print(json.dumps(summary, indent=2, default=str))
    return 0


def _init_validation_sqlite_schema() -> None:
    from sqlmodel import SQLModel

    from app.db.session import get_engine
    from app.models.external_catalog import (  # noqa: F401
        ExternalCatalogCreator,
        ExternalCatalogIssue,
        ExternalCatalogMatch,
        ExternalCatalogSource,
        ExternalCatalogSyncRun,
        ExternalCatalogVariant,
    )

    SQLModel.metadata.create_all(get_engine())


def _summarize_stored_issues(session) -> dict[str, object]:
    from sqlmodel import select

    from app.models.external_catalog import (
        ExternalCatalogCreator,
        ExternalCatalogIssue,
        ExternalCatalogVariant,
    )
    from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME

    issues = session.exec(
        select(ExternalCatalogIssue).where(ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME)
    ).all()
    pull_ok = sum(1 for i in issues if i.pull_count is not None)
    want_ok = sum(1 for i in issues if i.want_count is not None)
    cover_ok = sum(1 for i in issues if i.cover_image_url)
    creators = session.exec(select(ExternalCatalogCreator)).all()
    variants = session.exec(select(ExternalCatalogVariant)).all()
    return {
        "issues_stored": len(issues),
        "with_pull_count": pull_ok,
        "with_want_count": want_ok,
        "with_cover_image_url": cover_ok,
        "creator_rows": len(creators),
        "variant_rows": len(variants),
    }


if __name__ == "__main__":
    raise SystemExit(main())
