"""CLI for the ComicVine -> catalog_upc barcode backfill.

Dry-run (default) reports projected coverage and conflicts WITHOUT writing:

    python scripts/comicvine_barcode_backfill.py --limit-volumes 300

Resume a longer run (progress + cumulative stats persisted to the resume file):

    python scripts/comicvine_barcode_backfill.py --all --resume data/p101/cv_barcode_backfill.json

Only after a dry-run proves coverage and a low conflict rate, write to the catalog:

    python scripts/comicvine_barcode_backfill.py --all --write --resume data/p101/cv_barcode_backfill_write.json

The scanner/identification paths are untouched; this only fills catalog_upc so local
barcode matches succeed instead of hitting ComicVine on every scan.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_engine
from app.services.comicvine_barcode_backfill_service import BackfillStats, run_backfill
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter


def _pct(part: int, whole: int) -> str:
    return f"{(part / whole) * 100:.1f}%" if whole else "0.0%"


def _print_report(stats: BackfillStats, *, write: bool) -> None:
    checked = stats.issues_checked
    print("=" * 72)
    print(f"COMICVINE BARCODE BACKFILL  ({'WRITE' if write else 'DRY-RUN'})")
    print("=" * 72)
    print(f"  Volumes checked              {stats.volumes_checked:>10,}")
    print(f"  ComicVine requests made      {stats.requests_made:>10,}")
    print(f"  Total issues checked         {checked:>10,}")
    print(f"  Issues with barcode          {stats.cv_issues_with_barcode:>10,}   {_pct(stats.cv_issues_with_barcode, checked)}")
    print(f"  Usable full UPC+extension    {stats.usable_full:>10,}")
    print(f"  Base UPC only                {stats.base_only:>10,}")
    print(f"  Rejected by validation       {stats.rejected_validation:>10,}")
    print(f"  Duplicate barcode conflicts  {stats.duplicate_conflicts:>10,}")
    print(f"  Projected inserts            {stats.projected_inserts:>10,}")
    if write:
        print(f"  Rows written                 {stats.written:>10,}")

    usable = stats.usable_full + stats.base_only
    conflict_rate = _pct(stats.duplicate_conflicts, usable + stats.duplicate_conflicts)
    print("-" * 72)
    print(f"  Coverage of issues checked   {_pct(stats.projected_inserts, checked)} would gain a barcode")
    print(f"  Conflict rate (of usable)    {conflict_rate}")

    print("\n  By publisher (top 15 by projected inserts):")
    print(f"    {'publisher':<26}{'issues':>8}{'w/bc':>8}{'full':>8}{'base':>8}{'rej':>7}{'conf':>6}{'ins':>8}")
    pubs = sorted(stats.by_publisher.items(), key=lambda kv: kv[1].projected_inserts, reverse=True)[:15]
    for name, b in pubs:
        print(f"    {name[:25]:<26}{b.issues_checked:>8}{b.with_barcode:>8}{b.usable_full:>8}{b.base_only:>8}{b.rejected:>7}{b.conflicts:>6}{b.projected_inserts:>8}")

    print("\n  By year (with barcode coverage, sorted by year):")
    print(f"    {'year':<8}{'w/bc':>8}{'full':>8}{'base':>8}{'rej':>7}{'conf':>6}{'ins':>8}")
    years = sorted(stats.by_year.items(), key=lambda kv: kv[0])
    for year, b in years:
        if b.with_barcode == 0 and b.projected_inserts == 0:
            continue
        print(f"    {year:<8}{b.with_barcode:>8}{b.usable_full:>8}{b.base_only:>8}{b.rejected:>7}{b.conflicts:>6}{b.projected_inserts:>8}")

    print("\n  Sample rows:")
    header = f"    {'barcode':<19}{'localId':>8}  {'cvId':>8}  {'pub':<14}{'series':<26}{'#':<6}{'year':<6}status"
    print(header)
    for s in stats.samples[:40]:
        print(
            f"    {str(s['barcode']):<19}"
            f"{str(s['local_issue_id'] or '-'):>8}  "
            f"{str(s['comicvine_issue_id'] or '-'):>8}  "
            f"{str(s['publisher'])[:13]:<14}"
            f"{str(s['series'])[:25]:<26}"
            f"{str(s['issue_number'])[:5]:<6}"
            f"{str(s['year'] or '-'):<6}"
            f"{s['validation_status']}"
        )
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="ComicVine -> catalog_upc barcode backfill")
    parser.add_argument("--write", action="store_true", help="Insert catalog_upc rows (default: dry-run report only)")
    parser.add_argument("--limit-volumes", type=int, default=300, help="Max volumes to process this run (default 300)")
    parser.add_argument("--all", action="store_true", help="Process all volumes (ignores --limit-volumes)")
    parser.add_argument("--max-requests", type=int, default=None, help="Stop after N ComicVine requests")
    parser.add_argument("--resume", type=str, default=None, help="Resume/progress JSON file path")
    args = parser.parse_args()

    if args.write:
        print("WRITE MODE: catalog_upc rows will be inserted. Conflicts are never overwritten.\n")

    importer = ComicVineCatalogImporter()
    explain = importer.initialize_or_explain()
    if explain:
        raise SystemExit(f"ComicVine unavailable: {explain}")

    resume_path = Path(args.resume) if args.resume else None
    limit_volumes = None if args.all else args.limit_volumes

    with Session(get_engine()) as session:
        stats = run_backfill(
            session,
            importer,
            write=args.write,
            limit_volumes=limit_volumes,
            max_requests=args.max_requests,
            resume_path=resume_path,
        )

    _print_report(stats, write=args.write)


if __name__ == "__main__":
    main()
