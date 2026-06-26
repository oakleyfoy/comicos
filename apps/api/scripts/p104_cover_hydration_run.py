"""P104 cover hydration run CLI."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.models.catalog_cover_assets import (  # noqa: E402
    COVER_ASSET_STATUS_FAILED,
    CatalogCoverAsset,
    CatalogCoverHydrationRun,
)
from app.services.p104_cover_hydration_service import run_p104_hydration  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

LOGGER = logging.getLogger(__name__)
DEFAULT_OUT = Path("data/p104/cover_hydration_run.json")
PROGRESS_INTERVAL = 25


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _progress_line(
    *,
    run_id: int,
    completed: int,
    failed: int,
    skipped_no_url: int,
    pending_remaining: int,
    elapsed_s: float,
    covers_per_minute: float,
    catalog_issue_id: int,
    last_error: str | None,
) -> str:
    parts = [
        f"run_id={run_id}",
        f"completed={completed}",
        f"failed={failed}",
        f"skipped_no_url={skipped_no_url}",
        f"pending_remaining={pending_remaining}",
        f"elapsed={_format_elapsed(elapsed_s)}",
        f"covers_per_minute={covers_per_minute:.2f}",
        f"catalog_issue_id={catalog_issue_id}",
    ]
    if last_error:
        parts.append(f"last_error={last_error[:200]}")
    return "P104 progress " + " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="P104 cover hydration batch run")
    parser.add_argument("--limit", type=int, default=100, help="Max pending assets to hydrate this run")
    parser.add_argument(
        "--sync-limit",
        type=int,
        default=0,
        help="Optional queue-build before hydrate: upsert up to N asset rows (0 = existing queue only)",
    )
    parser.add_argument("--confirm-write", default=None, help="Must be YES to download")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if args.confirm_write != "YES":
        print("Refusing run without --confirm-write YES", file=sys.stderr)
        return 2

    started_at = time.perf_counter()
    last_error: str | None = None

    def on_asset_processed(
        processed: int,
        asset: CatalogCoverAsset,
        run: CatalogCoverHydrationRun,
        outcome: str,
    ) -> None:
        nonlocal last_error
        if outcome == COVER_ASSET_STATUS_FAILED and asset.last_error:
            last_error = asset.last_error
        if processed % PROGRESS_INTERVAL != 0:
            return
        elapsed = time.perf_counter() - started_at
        completed = int(run.completed)
        covers_per_minute = (completed / elapsed) * 60.0 if elapsed > 0 else 0.0
        pending_remaining = max(0, int(run.queued) - processed)
        line = _progress_line(
            run_id=int(run.id or 0),
            completed=completed,
            failed=int(run.failed),
            skipped_no_url=int(run.skipped_no_url),
            pending_remaining=pending_remaining,
            elapsed_s=elapsed,
            covers_per_minute=covers_per_minute,
            catalog_issue_id=int(asset.catalog_issue_id),
            last_error=last_error,
        )
        print(line, flush=True)

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine, expire_on_commit=False) as session:
        summary = run_p104_hydration(
            session,
            limit=args.limit,
            sync_limit=args.sync_limit,
            dry_run=False,
            on_asset_processed=on_asset_processed,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
