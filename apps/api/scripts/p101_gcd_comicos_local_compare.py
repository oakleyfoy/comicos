"""Fast local GCD vs ComicOS comparison (catalog cache + GCD SQLite only).

Usage:
  cd apps/api
  python scripts/p101_gcd_comicos_local_compare.py --refresh-cache
  python scripts/p101_gcd_comicos_local_compare.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.p101_catalog_cache_service import (  # noqa: E402
    DEFAULT_CACHE_PATH,
    YEAR_MAX,
    YEAR_MIN,
    CatalogCacheMatcher,
    comicos_counts_by_year,
    export_catalog_cache,
)
from app.services.p101_modern_catalog_audit_service import canonical_focus_publisher_label  # noqa: E402

DEFAULT_GCD = Path(r"C:\comic-os-p41-feed\data\p101\current\2026-06-15.db")
OUT_JSON = Path("data/p101/gcd_comicos_local_compare.json")
FOCUS_ORDER = ("Marvel", "DC", "Image", "Boom", "IDW", "Dark Horse", "Dynamite", "Valiant")

YEAR_EXPR = """
CASE
  WHEN i.key_date IS NOT NULL AND length(trim(i.key_date)) >= 4
       AND substr(i.key_date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'
    THEN CAST(substr(i.key_date, 1, 4) AS INTEGER)
  WHEN s.year_began BETWEEN 1900 AND 2100 THEN s.year_began
  ELSE NULL
END
"""


def _gcd_counts_by_year(gcd_path: Path) -> dict[int, int]:
    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    rows = conn.execute(
        f"""
        SELECT {YEAR_EXPR} AS yr, COUNT(*)
        FROM gcd_issue i JOIN gcd_series s ON s.id = i.series_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        GROUP BY yr ORDER BY yr
        """,
        (YEAR_MIN, YEAR_MAX),
    ).fetchall()
    conn.close()
    return {int(y): int(c) for y, c in rows if y is not None}


def _scan_missing(
    gcd_path: Path,
    matcher: CatalogCacheMatcher,
) -> tuple[Counter[int], Counter[str], int, int, list[dict]]:
    missing_by_year: Counter[int] = Counter()
    missing_by_focus: Counter[str] = Counter()
    missing_total = 0
    missing_with_barcode = 0
    samples: list[dict] = []

    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(
        f"""
        SELECT p.name, s.name, i.number, i.barcode, {YEAR_EXPR} AS yr
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE {YEAR_EXPR} BETWEEN ? AND ?
        """,
        (YEAR_MIN, YEAR_MAX),
    )
    while True:
        batch = cur.fetchmany(25000)
        if not batch:
            break
        for publisher, series, number, barcode, yr in batch:
            if yr is None:
                continue
            year = int(yr)
            if matcher.matches(
                publisher=str(publisher or ""),
                series=str(series or ""),
                issue_number=str(number or ""),
                year=year,
            ):
                continue
            missing_total += 1
            missing_by_year[year] += 1
            label = canonical_focus_publisher_label(str(publisher or ""))
            if label is not None:
                missing_by_focus[label] += 1
            has_bc = barcode is not None and str(barcode).strip() != ""
            if has_bc:
                missing_with_barcode += 1
                if len(samples) < 50:
                    samples.append(
                        {
                            "year": year,
                            "publisher": publisher,
                            "series": series,
                            "issue_number": number,
                            "barcode": str(barcode).strip()[:80],
                        }
                    )
    conn.close()
    return missing_by_year, missing_by_focus, missing_total, missing_with_barcode, samples


def _print_report(payload: dict) -> None:
    print("=" * 72)
    print("GCD vs ComicOS LOCAL COMPARE (2009-2026, read-only)")
    print(f"Elapsed: {payload['elapsed_seconds']:.1f}s")
    print(f"Catalog cache: {payload['catalog_cache']}")
    print(f"GCD DB: {payload['gcd_database']}")
    print()
    years = list(range(YEAR_MIN, YEAR_MAX + 1))
    print(f"{'Year':<6} {'ComicOS':>10} {'GCD':>10} {'Missing(est)':>12}")
    print("-" * 42)
    for y in years:
        row = payload["by_year"][str(y)]
        print(f"{y:<6} {row['comicos']:>10,} {row['gcd']:>10,} {row['missing_estimated']:>12,}")
    print()
    print("Missing by focus publisher (estimated):")
    for label in FOCUS_ORDER:
        print(f"  {label:<12} {payload['missing_by_publisher'].get(label, 0):>10,}")
    print()
    print(f"Missing GCD rows total:     {payload['missing_gcd_rows_total']:,}")
    print(f"Missing with barcode:       {payload['missing_with_barcode']:,}")
    print()
    print("Sample missing (up to 50, with barcode):")
    for s in payload["samples_missing_with_barcode"]:
        print(
            f"  {s['year']} | {s['publisher']} | {s['series'][:40]} #{s['issue_number']} | {s['barcode']}"
        )
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local GCD vs ComicOS compare")
    parser.add_argument("--gcd-db", default=str(DEFAULT_GCD))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--refresh-cache", action="store_true", help="Re-export ComicOS catalog to SQLite")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", default=str(OUT_JSON))
    args = parser.parse_args()

    cache_path = Path(args.cache)
    gcd_path = Path(args.gcd_db)
    if not gcd_path.exists():
        print(f"GCD DB not found: {gcd_path}", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    if args.refresh_cache or not cache_path.exists():
        print(f"Exporting ComicOS catalog -> {cache_path} ...", file=sys.stderr)
        with Session(get_engine()) as session:
            n = export_catalog_cache(session, cache_path)
        print(f"Cached {n:,} issues.", file=sys.stderr)

    comicos_by_year = comicos_counts_by_year(cache_path)
    gcd_by_year = _gcd_counts_by_year(gcd_path)
    matcher = CatalogCacheMatcher.from_sqlite(cache_path)
    missing_by_year, missing_by_focus, missing_total, missing_bc, samples = _scan_missing(gcd_path, matcher)
    elapsed = time.perf_counter() - t0

    by_year: dict[str, dict[str, int]] = {}
    for y in range(YEAR_MIN, YEAR_MAX + 1):
        by_year[str(y)] = {
            "comicos": int(comicos_by_year.get(y, 0)),
            "gcd": int(gcd_by_year.get(y, 0)),
            "missing_estimated": int(missing_by_year.get(y, 0)),
        }

    payload = {
        "report_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read_only_local_compare",
        "elapsed_seconds": round(elapsed, 2),
        "catalog_cache": str(cache_path),
        "gcd_database": str(gcd_path),
        "year_range": [YEAR_MIN, YEAR_MAX],
        "comicos_by_year": {str(k): v for k, v in sorted(comicos_by_year.items())},
        "gcd_by_year": {str(k): v for k, v in sorted(gcd_by_year.items())},
        "by_year": by_year,
        "missing_by_publisher": {k: int(missing_by_focus.get(k, 0)) for k in FOCUS_ORDER},
        "missing_gcd_rows_total": missing_total,
        "missing_with_barcode": missing_bc,
        "samples_missing_with_barcode": samples,
        "notes": [
            "One Postgres export to catalog cache; compare is local SQLite only.",
            "Missing = GCD row (2009-2026) with no catalog match on normalized publisher/series/issue (+ fuzzy series).",
        ],
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_report(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
