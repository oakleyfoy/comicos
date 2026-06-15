"""Import catalog-only JSONL snapshot into production (idempotent upsert, no deletes).

Usage:
  python scripts/p97_import_catalog_snapshot.py --input data/p97_catalog_snapshot.jsonl --dry-run
  python scripts/p97_import_catalog_snapshot.py --input data/p97_catalog_snapshot.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_catalog_snapshot_service import import_catalog_snapshot  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _resolve_input(path: str) -> Path:
    candidate = path.strip()
    resolved = Path(candidate)
    if not resolved.is_absolute():
        resolved = API_ROOT / resolved
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Import catalog-only JSONL snapshot (upsert, no deletes)")
    parser.add_argument("--database-url", default=None, help="Target DB (default: DATABASE_URL / production on Render)")
    parser.add_argument(
        "--input",
        default="data/p97_catalog_snapshot.jsonl",
        help="Input JSONL path (default: apps/api/data/p97_catalog_snapshot.jsonl)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count creates/updates without writing")
    args = parser.parse_args()

    input_path = _resolve_input(args.input)
    if not input_path.is_file():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    database_url = resolve_p97_database_url(args.database_url)
    print(f"Database: {describe_database_url(database_url)}")
    print(f"Input: {input_path}")
    print(f"Dry run: {bool(args.dry_run)}")

    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        stats = import_catalog_snapshot(session, input_path, dry_run=bool(args.dry_run))

    print("P97 CATALOG SNAPSHOT IMPORT")
    print(f"  dry_run={stats.dry_run}")
    print(f"  publishers created={stats.publishers_created} updated={stats.publishers_updated}")
    print(f"  series created={stats.series_created} updated={stats.series_updated}")
    print(f"  issues created={stats.issues_created} updated={stats.issues_updated}")
    print(f"  images created={stats.images_created} updated={stats.images_updated}")
    print(f"  skipped={stats.skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
