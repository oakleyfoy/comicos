"""P104 cover hydration benchmark CLI (timing by stage)."""

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
from app.services.p104_hydration_perf import P104PerformanceSummary  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

LOGGER = logging.getLogger(__name__)
DEFAULT_OUT = Path("data/p104/cover_hydration_benchmark.json")
PROGRESS_INTERVAL = 25


def _format_elapsed(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _print_performance_summary(perf_dict: dict) -> None:
    perf = P104PerformanceSummary()
    perf.assets_timed = int(perf_dict.get("assets_timed", 0))
    totals = perf_dict.get("totals_seconds", {})
    perf.url_resolve = float(totals.get("url_resolve", 0))
    perf.download = float(totals.get("download", 0))
    perf.staging_write = float(totals.get("staging_write", 0))
    perf.original_file_write = float(totals.get("original_file_write", 0))
    perf.derivative_resize_write = float(totals.get("derivative_resize_write", 0))
    perf.sha256 = float(totals.get("sha256", 0))
    perf.phash_ahash_dhash = float(totals.get("phash_ahash_dhash", 0))
    perf.color_histogram = float(totals.get("color_histogram", 0))
    perf.db_update_commit = float(totals.get("db_update_commit", 0))
    perf.total = float(totals.get("total", 0))
    for line in perf.format_lines():
        print(line, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P104 cover hydration benchmark (stage timings)")
    parser.add_argument("--limit", type=int, default=100, help="Covers to hydrate in this benchmark")
    parser.add_argument("--sync-limit", type=int, default=0)
    parser.add_argument("--confirm-write", default=None, help="Must be YES to download")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--download-workers", type=int, default=None)
    parser.add_argument("--process-workers", type=int, default=None)
    parser.add_argument("--downloads-per-minute", type=float, default=None)
    parser.add_argument("--reprocess", action="store_true", help="Re-hydrate completed assets")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    if args.confirm_write != "YES":
        print("Refusing benchmark without --confirm-write YES", file=sys.stderr)
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
        print(
            f"P104 benchmark progress run_id={int(run.id or 0)} "
            f"completed={completed} failed={int(run.failed)} "
            f"skipped_no_url={int(run.skipped_no_url)} pending_remaining={pending_remaining} "
            f"elapsed={_format_elapsed(elapsed)} covers_per_minute={covers_per_minute:.2f} "
            f"catalog_issue_id={int(asset.catalog_issue_id)}",
            flush=True,
        )

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    with Session(engine, expire_on_commit=False) as session:
        summary = run_p104_hydration(
            session,
            limit=args.limit,
            sync_limit=args.sync_limit,
            dry_run=False,
            reprocess=args.reprocess,
            download_workers=args.download_workers,
            process_workers=args.process_workers,
            downloads_per_minute=args.downloads_per_minute,
            on_asset_processed=on_asset_processed,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    progress = summary.get("progress", {})
    print(
        "P104 benchmark progress summary "
        f"run_id={progress.get('run_id')} "
        f"completed={progress.get('completed')} "
        f"failed={progress.get('failed')} "
        f"skipped_no_url={progress.get('skipped_no_url')} "
        f"elapsed={_format_elapsed(float(progress.get('elapsed_seconds', 0)))} "
        f"covers_per_minute={progress.get('covers_per_minute')}",
        flush=True,
    )
    _print_performance_summary(summary.get("performance", {}))
    print(json.dumps(summary, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
