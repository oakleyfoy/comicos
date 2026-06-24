"""CLI for the GCD -> catalog_upc barcode backfill.

Get a GCD dump from https://www.comics.org/download/ and load it into SQLite or Postgres.
Then dry-run (default; no writes):

    python scripts/gcd_barcode_backfill.py --gcd-db /path/to/gcd.sqlite

Resume / cap a run:

    python scripts/gcd_barcode_backfill.py --gcd-db gcd.sqlite --limit 50000 --resume data/p101/gcd_dryrun.json

Only after a clean dry-run (good match rate, low conflicts), write to the catalog:

    python scripts/gcd_barcode_backfill.py --gcd-db gcd.sqlite --write --resume data/p101/gcd_write.json

Safety: never overwrites existing catalog_upc rows, and skips any barcode already
present in comic_issue_barcodes (user-confirmed scans always win).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_engine
from app.services.gcd_barcode_import_service import (
    GcdBackfillStats,
    gcd_engine_from,
    run_gcd_backfill,
)


def _pct(part: int, whole: int) -> str:
    return f"{(part / whole) * 100:.1f}%" if whole else "0.0%"


def _print_report(stats: GcdBackfillStats, *, write: bool) -> None:
    print("=" * 72)
    print(f"GCD BARCODE BACKFILL  ({'WRITE' if write else 'DRY-RUN'})")
    print("=" * 72)
    print(f"  GCD total issues             {stats.gcd_total_issues:>10,}")
    print(f"  GCD rows checked (w/ barcode){stats.rows_checked:>10,}")
    print(f"  Rows with usable barcode     {stats.rows_with_barcode:>10,}")
    print(f"  Matched local issues         {stats.matched_local_issues:>10,}   {_pct(stats.matched_local_issues, stats.rows_with_barcode)}")
    print(f"  Unmatched GCD rows           {stats.unmatched_rows:>10,}   {_pct(stats.unmatched_rows, stats.rows_with_barcode)}")
    print(f"  Projected catalog_upc inserts{stats.projected_inserts:>10,}")
    print(f"  Duplicate conflicts          {stats.duplicate_conflicts:>10,}")
    print(f"  Rejected by validation       {stats.rejected_validation:>10,}")
    print(f"  Skipped (user-confirmed)     {stats.skipped_learned:>10,}")
    if write:
        print(f"  Rows written                 {stats.written:>10,}")

    usable = stats.projected_inserts + stats.duplicate_conflicts
    print("-" * 72)
    print(f"  Conflict rate (of insertable){_pct(stats.duplicate_conflicts, usable)}")

    print("\n  By publisher (top 15 by projected inserts):")
    print(f"    {'publisher':<28}{'w/bc':>8}{'match':>8}{'ins':>8}{'conf':>7}{'rej':>7}")
    pubs = sorted(stats.by_publisher.items(), key=lambda kv: kv[1].projected_inserts, reverse=True)[:15]
    for name, b in pubs:
        print(f"    {name[:27]:<28}{b.with_barcode:>8}{b.matched:>8}{b.projected_inserts:>8}{b.conflicts:>7}{b.rejected:>7}")

    print("\n  By year (sorted):")
    print(f"    {'year':<8}{'w/bc':>8}{'match':>8}{'ins':>8}{'conf':>7}{'rej':>7}")
    for year, b in sorted(stats.by_year.items(), key=lambda kv: kv[0]):
        if b.with_barcode == 0 and b.projected_inserts == 0:
            continue
        print(f"    {year:<8}{b.with_barcode:>8}{b.matched:>8}{b.projected_inserts:>8}{b.conflicts:>7}{b.rejected:>7}")

    print("\n  Sample rows:")
    print(f"    {'barcode':<19}{'localId':>8}  {'pub':<14}{'series':<26}{'#':<6}{'year':<6}status")
    for s in stats.samples[:40]:
        print(
            f"    {str(s['barcode']):<19}"
            f"{str(s['local_issue_id'] or '-'):>8}  "
            f"{str(s['publisher'])[:13]:<14}"
            f"{str(s['series'])[:25]:<26}"
            f"{str(s['issue_number'])[:5]:<6}"
            f"{str(s['year'] or '-'):<6}"
            f"{s['validation_status']}"
        )
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="GCD -> catalog_upc barcode backfill")
    parser.add_argument("--gcd-db", required=True, help="GCD dump: SQLite file path or SQLAlchemy URL")
    parser.add_argument("--write", action="store_true", help="Insert catalog_upc rows (default: dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Max GCD barcode rows to process this run")
    parser.add_argument("--resume", type=str, default=None, help="Resume/progress JSON file path")
    args = parser.parse_args()

    if args.write:
        print("WRITE MODE: new catalog_upc rows will be inserted. Existing rows and learned mappings are never touched.\n")

    gcd = gcd_engine_from(args.gcd_db)
    resume_path = Path(args.resume) if args.resume else None

    with Session(get_engine()) as session:
        stats = run_gcd_backfill(session, gcd, write=args.write, limit=args.limit, resume_path=resume_path)

    _print_report(stats, write=args.write)


if __name__ == "__main__":
    main()
