"""P98 — Expand BUILD_ISSUE_SHELLS volumes from discovered issue counts.

Default is dry-run (no DB writes). Pass --apply to commit.

Examples:
  python scripts/p98_expand_issue_shells.py --publisher Marvel --top 50
  python scripts/p98_expand_issue_shells.py --apply --limit-volumes 100
"""

from __future__ import annotations

import argparse
import json
import sys

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_issue_shell_expansion_service import (  # noqa: E402
    ExpansionCandidate,
    ExpansionStats,
    default_progress_path,
    default_queue_path,
    expand_action_queue,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _progress(stats: ExpansionStats, cand: ExpansionCandidate) -> None:
    _log(
        f"[{stats.elapsed_seconds:7.1f}s] expanded={stats.volumes_expanded} "
        f"vol#{cand.comicvine_volume_id} '{cand.volume_name[:40]}' | "
        f"issues +{stats.issues_created} variants +{stats.variants_created} "
        f"skipped={stats.volumes_skipped} failed={stats.volumes_failed}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 synthetic issue shell expansion")
    parser.add_argument("--publisher", type=str, default=None)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--limit-volumes", type=int, default=None)
    parser.add_argument("--apply", action="store_true", help="Commit changes (default: dry-run)")
    parser.add_argument("--commit-every", type=int, default=10)
    parser.add_argument("--no-resume", action="store_true", help="Ignore progress file resume state")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    dry_run = not args.apply
    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    _log("P98 ISSUE SHELL EXPANSION — startup")
    _log(f"  target database: {describe_database_url(database_url)}")
    _log(f"  mode:            {'DRY RUN' if dry_run else 'APPLY'}")
    _log(f"  publisher:       {args.publisher or '(all major, queue order)'}")
    _log(f"  top:             {args.top}")
    _log(f"  limit_volumes:   {args.limit_volumes}")
    _log(f"  queue file:      {default_queue_path()}")
    _log(f"  progress file:   {default_progress_path()}")

    with Session(engine) as session:
        stats = expand_action_queue(
            session,
            publisher=args.publisher,
            top=args.top,
            limit_volumes=args.limit_volumes,
            queue_path=default_queue_path(),
            progress_path=default_progress_path(),
            commit_every=args.commit_every,
            dry_run=dry_run,
            resume_from_progress=not args.no_resume,
            progress_callback=_progress,
        )

    if args.json:
        print(json.dumps(stats.as_dict()))
        return

    _log("")
    _log("P98 ISSUE SHELL EXPANSION SUMMARY")
    _log(f"  Selected:   {stats.volumes_selected}")
    _log(f"  Expanded:   {stats.volumes_expanded}")
    _log(f"  Skipped:    {stats.volumes_skipped}")
    _log(f"  Failed:     {stats.volumes_failed}")
    _log(f"  Issues + :  {stats.issues_created}")
    _log(f"  Variants +: {stats.variants_created}")
    _log(f"  Elapsed:    {stats.elapsed_seconds:.1f}s")
    if stats.by_publisher:
        _log("  By publisher:")
        for pub, bucket in sorted(stats.by_publisher.items()):
            _log(
                f"    {pub}: volumes={bucket.get('volumes_expanded', 0)} "
                f"issues={bucket.get('issues_created', 0)} "
                f"variants={bucket.get('variants_created', 0)}"
            )
    if dry_run:
        _log("  (dry run — pass --apply to write)")
    sys.exit(0)


if __name__ == "__main__":
    main()
