from __future__ import annotations

import argparse
import logging
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_engine  # noqa: E402
from app.services.catalog_bulk_fingerprint_service import run_bulk_fingerprints  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 bulk catalog cover fingerprints")
    parser.add_argument("--missing-only", action="store_true", default=True)
    parser.add_argument("--failed-only", action="store_true")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--batch-size", type=int, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    batch = args.batch_size or get_settings().catalog_import_batch_size
    with Session(get_engine()) as session:
        summary = run_bulk_fingerprints(
            session,
            missing_only=not args.failed_only,
            limit=args.limit,
            dry_run=args.dry_run,
            resume=args.resume,
            batch_size=batch,
        )
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
