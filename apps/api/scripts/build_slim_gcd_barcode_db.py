"""Build a slim, deployable GCD barcode-lookup DB.

The full GCD SQLite dump (~6.5 GB) is too large to ship to the API host, so the
production scanner cannot resolve barcodes that exist in GCD. This builds a small
SQLite file containing only what ``gcd_barcode_search_service`` needs:

    * gcd_issue rows that carry a barcode / isbn (or UPC-bearing notes)
    * the gcd_series they reference
    * the gcd_publisher those series reference

Resulting DB is a drop-in for ``GCD_SQLITE_PATH`` and is typically <200 MB.

Usage:
    python scripts/build_slim_gcd_barcode_db.py [SOURCE_DB] [OUTPUT_DB]
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DEFAULT_SOURCE = Path("data/p101/current/2026-06-15.db")
DEFAULT_OUTPUT = Path("data/p101/current/gcd-barcode-slim.db")


def build(source: Path, output: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"source GCD db not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()

    src = sqlite3.connect(source)
    out = sqlite3.connect(output)
    out.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE gcd_series (
            id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER
        );
        CREATE TABLE gcd_issue (
            id INTEGER PRIMARY KEY, number TEXT, series_id INTEGER,
            key_date TEXT, title TEXT, barcode TEXT, notes TEXT, isbn TEXT
        );
        """
    )

    issue_rows = src.execute(
        """
        SELECT id, number, series_id, key_date, title, barcode, notes, isbn
        FROM gcd_issue
        WHERE (barcode IS NOT NULL AND TRIM(barcode) <> '')
           OR (isbn IS NOT NULL AND TRIM(isbn) <> '')
           OR (notes LIKE '%UPC%' OR notes LIKE '%barcode%' OR notes LIKE '%bar code%')
        """
    ).fetchall()
    out.executemany(
        "INSERT INTO gcd_issue (id, number, series_id, key_date, title, barcode, notes, isbn)"
        " VALUES (?,?,?,?,?,?,?,?)",
        issue_rows,
    )

    series_ids = {r[2] for r in issue_rows if r[2] is not None}
    series_rows = []
    pub_ids: set[int] = set()
    for sid in series_ids:
        row = src.execute(
            "SELECT id, name, year_began, publisher_id FROM gcd_series WHERE id = ?",
            (sid,),
        ).fetchone()
        if row:
            series_rows.append(row)
            if row[3] is not None:
                pub_ids.add(row[3])
    out.executemany(
        "INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (?,?,?,?)",
        series_rows,
    )

    pub_rows = []
    for pid in pub_ids:
        row = src.execute("SELECT id, name FROM gcd_publisher WHERE id = ?", (pid,)).fetchone()
        if row:
            pub_rows.append(row)
    out.executemany("INSERT INTO gcd_publisher (id, name) VALUES (?,?)", pub_rows)

    out.executescript(
        """
        CREATE INDEX ix_slim_issue_barcode ON gcd_issue(barcode);
        CREATE INDEX ix_slim_issue_series ON gcd_issue(series_id);
        CREATE INDEX ix_slim_series_pub ON gcd_series(publisher_id);
        """
    )
    out.commit()
    out.execute("VACUUM")
    out.commit()
    src.close()
    out.close()

    size_mb = output.stat().st_size / (1024 * 1024)
    print(
        f"built slim GCD db: {output} "
        f"issues={len(issue_rows)} series={len(series_rows)} publishers={len(pub_rows)} "
        f"size={size_mb:.1f} MB"
    )


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    build(source, output)
