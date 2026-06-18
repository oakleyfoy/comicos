"""P101-04 batched production catalog import (commit per batch, resume-safe).

Usage:
  python scripts/p101_import_catalog_batched.py \\
    --database-url "$DATABASE_URL" \\
    --input data/p97_full_catalog_promotion.jsonl \\
    --verbose

  python scripts/p101_import_catalog_batched.py --resume --database-url ... --input ...
  python scripts/p101_import_catalog_batched.py --verify-only --database-url ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p101_batched_catalog_import_service import (  # noqa: E402
    DEFAULT_BATCH_SIZES,
    PHASE_ORDER,
    catalog_table_counts,
    default_state_path,
    run_batched_catalog_import,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def _resolve_input(path: str) -> Path:
    candidate = Path(path.strip())
    if not candidate.is_absolute():
        candidate = API_ROOT / candidate
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="P101-04 batched catalog snapshot import")
    parser.add_argument("--database-url", default=None, help="Production DB URL (required for live import)")
    parser.add_argument(
        "--input",
        default="data/p97_full_catalog_promotion.jsonl",
        help="Catalog JSONL snapshot path",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Override batch size for all phases (defaults: publishers=100, series=500, issues=1000, images=1000)",
    )
    parser.add_argument(
        "--start-phase",
        choices=PHASE_ORDER,
        default=None,
        help="Begin at this phase (earlier phases assumed already applied in DB)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count upserts without committing")
    parser.add_argument("--resume", action="store_true", help="Continue from data/p101/batched_import_state.json")
    parser.add_argument("--verbose", action="store_true", help="Log index-build detail")
    parser.add_argument(
        "--state-file",
        default=None,
        help="Resume state JSON path (default: data/p101/batched_import_state.json)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Print catalog table counts and exit (no import)",
    )
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    if not args.database_url and not args.verify_only:
        print("ERROR: --database-url is required for live import.", file=sys.stderr)
        return 2

    engine = get_p97_engine(database_url)
    if args.verify_only:
        with Session(engine) as session:
            print(f"Database: {describe_database_url(database_url)}")
            print(catalog_table_counts(session))
        return 0

    input_path = _resolve_input(args.input)
    batch_sizes = dict(DEFAULT_BATCH_SIZES)
    if args.batch_size is not None:
        for phase in PHASE_ORDER:
            batch_sizes[phase] = int(args.batch_size)

    state_path = Path(args.state_file) if args.state_file else default_state_path()
    print(f"Database: {describe_database_url(database_url)}")
    print(f"Input: {input_path}")
    print(f"State: {state_path}")
    print(f"Dry run: {bool(args.dry_run)}")
    print(f"Resume: {bool(args.resume)}")
    print(f"Batch sizes: {batch_sizes}")

    with Session(engine) as session:
        run_batched_catalog_import(
            session,
            input_path=input_path,
            database_target=describe_database_url(database_url),
            dry_run=bool(args.dry_run),
            verbose=bool(args.verbose),
            batch_sizes=batch_sizes,
            start_phase=args.start_phase,
            resume=bool(args.resume),
            state_path=state_path,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
