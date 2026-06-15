"""Export catalog-only JSONL snapshot for P97 production sync.

Usage:
  python scripts/p97_export_catalog_snapshot.py --output data/p97_catalog_snapshot.jsonl
  python scripts/p97_export_catalog_snapshot.py --volume-id 160294 --output data/p97_absolute_batman.jsonl
  python scripts/p97_export_catalog_snapshot.py --full --output data/p97_full_catalog.jsonl
"""

from __future__ import annotations

import argparse
import sys

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_catalog_snapshot_service import export_catalog_snapshot  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _resolve_output(path: str) -> str:
    candidate = path.strip()
    if not candidate:
        return str(API_ROOT / "data" / "p97_catalog_snapshot.jsonl")
    from pathlib import Path

    resolved = Path(candidate)
    if not resolved.is_absolute():
        resolved = API_ROOT / resolved
    return str(resolved)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export catalog-only JSONL snapshot (no user/inventory data)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--output",
        default="data/p97_catalog_snapshot.jsonl",
        help="Output JSONL path (default: apps/api/data/p97_catalog_snapshot.jsonl)",
    )
    parser.add_argument(
        "--volume-id",
        action="append",
        type=int,
        default=None,
        help="ComicVine volume id to export (repeatable). Default: all ComicVine-linked catalog rows",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Export entire catalog_publisher/series/issue/image tables (large)",
    )
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    output_path = _resolve_output(args.output)
    print(f"Database: {describe_database_url(database_url)}")
    print(f"Output: {output_path}")

    from pathlib import Path

    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        stats = export_catalog_snapshot(
            session,
            Path(output_path),
            volume_ids=args.volume_id,
            full_catalog=bool(args.full),
        )

    print("P97 CATALOG SNAPSHOT EXPORT")
    print(f"  publishers={stats.publishers}")
    print(f"  series={stats.series}")
    print(f"  issues={stats.issues}")
    print(f"  images={stats.images}")
    if stats.volume_ids:
        print(f"  volume_ids={stats.volume_ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
