"""Report remaining GCD clean_primary_candidate rows vs catalog coverage by publisher.

NOTE: Counts use the import-matrix scan (cache matcher + classify). The write loop
applies additional Postgres guards (GCD issue ids, series+issue keys, live UPC/learned
barcodes). Remaining clean candidates here can be **higher** than rows a write batch
will actually insert. Use dry-run/benchmark-dry-run or a small --limit write to verify
before large batches. TODO: align with write-loop eligibility exactly.

Usage:
  cd apps/api
  python scripts/p102_gcd_remaining.py --publisher DC --year-from 2009 --year-to 2026
  python scripts/p102_gcd_remaining.py --year-from 2009 --year-to 2026
  python scripts/p102_gcd_remaining.py --refresh-cache --json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import (  # noqa: E402
    compute_gcd_remaining_stats,
    ensure_catalog_cache,
    resolve_cache_path,
    resolve_gcd_path,
)
from app.services.p101_catalog_cache_service import DEFAULT_CACHE_PATH  # noqa: E402
from app.services.p102_gcd_modern_acquisition_service import FOCUS_PUBLISHERS  # noqa: E402


def _fmt(n: int) -> str:
    return f"{n:,}"


def main() -> int:
    parser = argparse.ArgumentParser(description="GCD remaining clean candidates by publisher")
    parser.add_argument("--publisher", default=None, help="Focus publisher (default: all focus publishers)")
    parser.add_argument("--year-from", type=int, default=2009)
    parser.add_argument("--year-to", type=int, default=2026)
    parser.add_argument("--gcd-db", default=None)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    gcd_path = resolve_gcd_path(args.gcd_db)
    cache_path = resolve_cache_path(args.cache or str(DEFAULT_CACHE_PATH))
    if not gcd_path.exists():
        print(f"GCD database missing: {gcd_path}", file=sys.stderr)
        return 2

    publishers = [args.publisher] if args.publisher else list(FOCUS_PUBLISHERS)
    if args.publisher and args.publisher not in FOCUS_PUBLISHERS:
        print(f"WARN: {args.publisher} not in focus list {FOCUS_PUBLISHERS}", file=sys.stderr)

    t0 = time.perf_counter()
    with Session(get_engine()) as session:
        ensure_catalog_cache(session, cache_path, refresh=args.refresh_cache)

    rows: list[dict] = []
    for pub in publishers:
        stats = compute_gcd_remaining_stats(
            gcd_path=gcd_path,
            cache_path=cache_path,
            publisher=pub,
            year_from=args.year_from,
            year_to=args.year_to,
        )
        rows.append(stats.to_dict())

    elapsed = round(time.perf_counter() - t0, 1)
    payload = {
        "report_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "year_from": args.year_from,
        "year_to": args.year_to,
        "gcd_database": str(gcd_path),
        "catalog_cache": str(cache_path),
        "elapsed_seconds": elapsed,
        "publishers": rows,
        "totals": {
            "remaining_clean_candidates": sum(r["remaining_clean_candidates"] for r in rows),
            "already_in_comicos": sum(r["already_in_comicos"] for r in rows),
            "total_clean_primary": sum(r["total_clean_primary"] for r in rows),
            "gcd_rows_in_scope": sum(r["gcd_rows_in_scope"] for r in rows),
        },
    }

    if args.json:
        print(json.dumps(payload, indent=2))
        return 0

    print("=" * 72)
    print("P102 GCD REMAINING (clean_primary_candidate scope)")
    print("WARN: remaining count is matrix/classify only; write path may insert 0 if")
    print("      GCD ids / series+issue / barcode guards already cover these rows.")
    print(f"Years: {args.year_from}-{args.year_to}  GCD: {gcd_path.name}")
    print(f"Cache: {cache_path}  Elapsed: {elapsed}s")
    print("=" * 72)
    for r in rows:
        print(f"\nPublisher: {r['publisher']}")
        print(f"  Remaining clean candidates: {_fmt(int(r['remaining_clean_candidates']))}")
        print(f"  Already imported:             {_fmt(int(r['already_in_comicos']))}")
        print(f"  Total clean:                  {_fmt(int(r['total_clean_primary']))}")
        print(f"  GCD rows in scope:            {_fmt(int(r['gcd_rows_in_scope']))}")
        print(
            f"  Other classified: variants={_fmt(int(r['variants']))} "
            f"reprints={_fmt(int(r['reprints']))} conflicts={_fmt(int(r['conflicts']))}"
        )
    if len(rows) > 1:
        t = payload["totals"]
        print("\n" + "-" * 72)
        print("ALL PUBLISHERS (totals)")
        print(f"  Remaining clean candidates: {_fmt(int(t['remaining_clean_candidates']))}")
        print(f"  Already imported:             {_fmt(int(t['already_in_comicos']))}")
        print(f"  Total clean:                  {_fmt(int(t['total_clean_primary']))}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
