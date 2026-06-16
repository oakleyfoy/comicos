"""P98-03/04 — issue + UNKNOWN variant shells (volume-driven, resumable, safe).

Examples:
  python scripts/p98_build_issue_shells.py --limit-volumes 25 --verbose
  python scripts/p98_build_issue_shells.py --publisher Marvel --commit-every 50
  python scripts/p98_build_issue_shells.py --start-after-volume-id 12345 --refresh
  python scripts/p98_build_issue_shells.py --dry-run --limit-volumes 100 --json
"""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.models.universe import UniverseVolume  # noqa: E402
from app.services.universe.universe_issue_service import (  # noqa: E402
    IssueShellBuildStats,
    build_issue_shells,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(message: str) -> None:
    print(message, flush=True)


def _progress(stats: IssueShellBuildStats, volume: UniverseVolume) -> None:
    _log(
        f"[{stats.elapsed_seconds:7.1f}s] processed={stats.processed} "
        f"vol#{volume.comicvine_volume_id} '{volume.name[:48]}' | "
        f"issues +{stats.issues_created}/~{stats.issues_updated} "
        f"variants +{stats.variants_created}/~{stats.variants_updated} "
        f"skip_existing={stats.skipped_existing} skip_no_source={stats.skipped_no_source} "
        f"failed={stats.failed}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build universe issue shells (P98-03/04)")
    parser.add_argument("--limit-volumes", type=int, default=None)
    parser.add_argument("--publisher", type=str, default=None)
    parser.add_argument("--start-after-volume-id", type=int, default=None)
    parser.add_argument("--commit-every", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Override target DB (defaults to DATABASE_URL / .env). The skeleton "
        "volumes must live in this DB or 0 volumes will be selected.",
    )
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        from app.services.universe.universe_issue_service import _select_universe_volumes

        selected = _select_universe_volumes(
            session,
            publisher=args.publisher,
            start_after_volume_id=args.start_after_volume_id,
            limit_volumes=args.limit_volumes,
        )
        _log("P98 ISSUE SHELL BUILD — startup")
        _log(f"  target database:       {describe_database_url(database_url)}")
        _log(f"  total universe volumes selected: {len(selected)}")
        _log(f"  dry_run:               {args.dry_run}")
        _log(f"  limit_volumes:         {args.limit_volumes}")
        _log(f"  publisher filter:      {args.publisher or '(none)'}")
        _log(f"  start_after_volume_id: {args.start_after_volume_id}")
        _log(f"  refresh mode:          {args.refresh}")
        _log(f"  commit interval:       {args.commit_every}")
        if not selected:
            _log("  Nothing to do (0 volumes matched). Did you run p98_build_volumes.py?")

        stats = build_issue_shells(
            session,
            limit_volumes=args.limit_volumes,
            publisher=args.publisher,
            start_after_volume_id=args.start_after_volume_id,
            commit_every=args.commit_every,
            dry_run=args.dry_run,
            refresh=args.refresh,
            progress_every=1 if args.verbose else 25,
            progress_callback=_progress,
        )

    if args.json:
        print(json.dumps(stats.as_dict()))
        return

    _log("")
    _log("P98 ISSUE SHELL BUILD SUMMARY")
    _log(f"  Selected volumes:        {stats.selected_volumes}")
    _log(f"  Processed:               {stats.processed}")
    _log(f"  Skipped existing:        {stats.skipped_existing}")
    _log(f"  Skipped no source issues:{stats.skipped_no_source}")
    _log(f"  Failed:                  {stats.failed}")
    _log(f"  Issues created:          {stats.issues_created}")
    _log(f"  Issues updated:          {stats.issues_updated}")
    _log(f"  Variants created:        {stats.variants_created}")
    _log(f"  Variants updated:        {stats.variants_updated}")
    _log(f"  Elapsed:                 {stats.elapsed_seconds:.1f}s")
    if stats.failed_volume_ids:
        _log(f"  Failed volume ids:       {stats.failed_volume_ids[:50]}")
    if args.dry_run:
        _log("  (dry run — no rows committed)")
    sys.exit(0)


if __name__ == "__main__":
    main()
