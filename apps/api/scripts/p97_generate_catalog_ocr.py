from __future__ import annotations

import argparse
import logging
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.catalog_bulk_ocr_service import count_ocr_remaining, run_bulk_ocr  # noqa: E402
from p97_db import ensure_p97_tesseract_env, get_p97_engine, resolve_p97_database_url  # noqa: E402

LOGGER = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 bulk catalog cover OCR")
    parser.add_argument("--missing-only", action="store_true", default=True)
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Repeat batches of --limit until no ready covers lack OCR metadata",
    )
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL (default: apps/api/.env DATABASE_URL or comic_os on localhost:5433)",
    )
    args = parser.parse_args()
    ensure_p97_tesseract_env()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    batch = args.batch_size or get_settings().catalog_import_batch_size
    database_url = resolve_p97_database_url(args.database_url)
    LOGGER.info("database=%s", database_url.split("@")[-1] if "@" in database_url else database_url)

    engine = get_p97_engine(database_url)
    batch_resume = args.resume
    batch_num = 0
    last_summary: dict | None = None

    while True:
        batch_num += 1
        with Session(engine) as session:
            last_summary = run_bulk_ocr(
                session,
                missing_only=not args.failed_only,
                limit=args.limit,
                dry_run=args.dry_run,
                resume=batch_resume,
                batch_size=batch,
            )
        print(last_summary)
        if not args.loop:
            break
        with Session(engine) as session:
            remaining = count_ocr_remaining(session)
        seen = int(last_summary.get("total_seen") or 0)
        LOGGER.info(
            "ocr loop batch=%s remaining=%s total_seen=%s",
            batch_num,
            remaining,
            seen,
        )
        if remaining <= 0 or seen <= 0:
            LOGGER.info("ocr loop complete after %s batch(es)", batch_num)
            break
        batch_resume = True

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
