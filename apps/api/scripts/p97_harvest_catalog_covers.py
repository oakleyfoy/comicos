from __future__ import annotations

import argparse
import logging
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.services.catalog_cover_harvest_service import run_cover_harvest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 catalog cover harvest (offline; respect source terms)")
    parser.add_argument("--source", default=None, help="Limit to catalog_image.source (e.g. COMICVINE)")
    parser.add_argument("--missing-only", action="store_true", default=True)
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument(
        "--repair-missing-files",
        action="store_true",
        help="Re-download ready covers whose local_path file is missing on disk",
    )
    parser.add_argument(
        "--repair-missing-fingerprints",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="With --repair-missing-files, only repair ready covers that lack fingerprints (default: on)",
    )
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = get_settings()
    sleep = args.sleep_seconds if args.sleep_seconds is not None else settings.catalog_import_sleep_seconds
    batch = args.batch_size or settings.catalog_import_batch_size
    missing_only = not args.failed_only and not args.repair_missing_files
    repair_fp_only = args.repair_missing_fingerprints
    if args.repair_missing_files and repair_fp_only is None:
        repair_fp_only = True
    with Session(get_engine()) as session:
        summary = run_cover_harvest(
            session,
            source=args.source,
            missing_only=missing_only,
            failed_only=args.failed_only,
            repair_missing_files=args.repair_missing_files,
            repair_missing_fingerprints_only=bool(repair_fp_only),
            limit=args.limit,
            dry_run=args.dry_run,
            resume=args.resume,
            sleep_seconds=sleep,
            batch_size=batch,
        )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
