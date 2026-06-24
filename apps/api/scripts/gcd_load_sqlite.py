"""Convert a Grand Comics Database (GCD) MySQL dump into a small local SQLite file,
then (by default) run the GCD barcode backfill in dry-run mode.

Why: the GCD dump is a multi-GB mysqldump .sql with ~2M issues and dozens of tables.
We only need three tables and a handful of columns for barcode backfill, so this streams
the dump line by line (never loading it all into memory) and writes just what we need to
``data/p101/gcd.sqlite``.

One-command flow after you download the dump from https://www.comics.org/download/:

    cd apps/api
    python scripts/gcd_load_sqlite.py --dump /path/to/gcd_dump.sql

    # gzipped dump also works:
    python scripts/gcd_load_sqlite.py --dump /path/to/gcd_dump.sql.gz

    # convert only, skip the dry-run:
    python scripts/gcd_load_sqlite.py --dump gcd_dump.sql --no-run

This NEVER writes to ComicOS. The follow-up backfill runs dry-run only.
"""

from __future__ import annotations

import argparse
import gzip
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import IO, Iterable

# table -> ordered columns we keep (must exist in the dump's CREATE TABLE)
TARGET_COLUMNS: dict[str, list[str]] = {
    "gcd_publisher": ["id", "name"],
    "gcd_series": ["id", "name", "year_began", "publisher_id"],
    "gcd_issue": ["id", "number", "barcode", "key_date", "series_id"],
}

INT_COLUMNS = {"id", "year_began", "publisher_id", "series_id"}
BATCH = 5000

DEFAULT_OUT = Path("data/p101/gcd.sqlite")
DEFAULT_RESUME = Path("data/p101/gcd_dryrun.json")
DEFAULT_LIMIT = 50000

_CREATE_RE = re.compile(r"CREATE TABLE `([^`]+)`")
_INSERT_RE = re.compile(r"INSERT INTO `([^`]+)`")
_COLNAME_RE = re.compile(r"^`([^`]+)`")


def open_dump(path: Path) -> IO[str]:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _read_create_columns(handle: Iterable[str]) -> list[str]:
    """Consume a CREATE TABLE body and return ordered column names (skips keys/constraints)."""
    cols: list[str] = []
    for line in handle:
        stripped = line.strip()
        if stripped.startswith(")"):
            break
        m = _COLNAME_RE.match(stripped)
        if m:  # key/constraint lines start with a keyword, not a backtick
            cols.append(m.group(1))
    return cols


def _parse_value_tuples(values: str) -> list[list[object]]:
    """Parse the ``(...),(...),...`` payload of an INSERT into lists of Python values.

    Handles single-quoted strings with backslash escapes and unquoted NULL/number tokens.
    """
    rows: list[list[object]] = []
    i, n = 0, len(values)
    while i < n:
        if values[i] != "(":
            i += 1
            continue
        i += 1
        field_chars: list[str] = []
        fields: list[object] = []
        in_str = False
        quoted = False
        while i < n:
            c = values[i]
            if in_str:
                if c == "\\" and i + 1 < n:
                    field_chars.append(values[i + 1])
                    i += 2
                    continue
                if c == "'":
                    in_str = False
                    i += 1
                    continue
                field_chars.append(c)
                i += 1
                continue
            if c == "'":
                in_str = True
                quoted = True
                i += 1
                continue
            if c == "," or c == ")":
                token = "".join(field_chars)
                if quoted:
                    fields.append(token)
                else:
                    stripped = token.strip()
                    fields.append(None if stripped.upper() == "NULL" else stripped)
                field_chars = []
                quoted = False
                if c == ")":
                    i += 1
                    rows.append(fields)
                    break
                i += 1
                continue
            field_chars.append(c)
            i += 1
    return rows


def _explicit_columns(head: str) -> list[str] | None:
    """If the INSERT lists columns (`--complete-insert`), return them; else None."""
    paren = head.find("(")
    if paren == -1:
        return None
    return re.findall(r"`([^`]+)`", head[paren:])


def convert_dump_to_sqlite(dump_path: Path, out_path: Path) -> dict[str, int]:
    """Stream the mysqldump and load only the barcode-backfill tables into SQLite.

    Returns row counts per table.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(str(out_path))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("CREATE TABLE gcd_publisher (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute(
        "CREATE TABLE gcd_series (id INTEGER PRIMARY KEY, name TEXT, year_began INTEGER, publisher_id INTEGER)"
    )
    conn.execute(
        "CREATE TABLE gcd_issue (id INTEGER PRIMARY KEY, number TEXT, barcode TEXT, key_date TEXT, series_id INTEGER)"
    )

    insert_sql = {
        "gcd_publisher": "INSERT OR REPLACE INTO gcd_publisher (id, name) VALUES (?, ?)",
        "gcd_series": "INSERT OR REPLACE INTO gcd_series (id, name, year_began, publisher_id) VALUES (?, ?, ?, ?)",
        "gcd_issue": "INSERT OR REPLACE INTO gcd_issue (id, number, barcode, key_date, series_id) VALUES (?, ?, ?, ?, ?)",
    }
    counts = {t: 0 for t in TARGET_COLUMNS}
    schema: dict[str, list[str]] = {}

    with open_dump(dump_path) as handle:
        for line in handle:
            stripped = line.lstrip()

            if stripped.startswith("CREATE TABLE"):
                m = _CREATE_RE.match(stripped)
                if m and m.group(1) in TARGET_COLUMNS:
                    schema[m.group(1)] = _read_create_columns(handle)
                continue

            if not stripped.startswith("INSERT INTO"):
                continue
            m = _INSERT_RE.match(stripped)
            table = m.group(1) if m else None
            if table not in TARGET_COLUMNS:
                # Skip a possibly multi-line non-target INSERT without parsing it.
                while not stripped.rstrip().endswith(";"):
                    try:
                        stripped = next(handle)
                    except StopIteration:
                        break
                continue

            statement = line
            while not statement.rstrip().endswith(";"):
                try:
                    statement += next(handle)
                except StopIteration:
                    break

            head, _, values = statement.partition(" VALUES")
            if not values:
                continue
            columns = _explicit_columns(head) or schema.get(table)
            if not columns:
                raise SystemExit(f"Could not determine columns for {table} (no CREATE TABLE seen)")
            try:
                positions = [columns.index(c) for c in TARGET_COLUMNS[table]]
            except ValueError as exc:
                raise SystemExit(f"{table} dump missing a needed column: {exc}") from exc

            batch: list[tuple] = []
            for row in _parse_value_tuples(values.rstrip().rstrip(";")):
                if max(positions) >= len(row):
                    continue
                picked = []
                for col, pos in zip(TARGET_COLUMNS[table], positions):
                    val = row[pos]
                    picked.append(_to_int(val) if col in INT_COLUMNS else val)
                batch.append(tuple(picked))
                if len(batch) >= BATCH:
                    conn.executemany(insert_sql[table], batch)
                    counts[table] += len(batch)
                    batch = []
            if batch:
                conn.executemany(insert_sql[table], batch)
                counts[table] += len(batch)
            conn.commit()

    conn.execute("CREATE INDEX IF NOT EXISTS ix_gcd_issue_series ON gcd_issue (series_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_gcd_issue_barcode ON gcd_issue (barcode)")
    conn.commit()
    conn.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a GCD MySQL dump into SQLite, then dry-run the barcode backfill")
    parser.add_argument("--dump", required=True, help="Path to GCD mysqldump .sql or .sql.gz")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help=f"Output SQLite path (default {DEFAULT_OUT})")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Row cap for the follow-up dry-run")
    parser.add_argument("--no-run", action="store_true", help="Only convert; do not run the dry-run")
    args = parser.parse_args()

    dump_path = Path(args.dump)
    if not dump_path.exists():
        raise SystemExit(f"Dump not found: {dump_path}")
    out_path = Path(args.out)

    print(f"Converting {dump_path} -> {out_path} (streaming; only gcd_issue/gcd_series/gcd_publisher)...")
    counts = convert_dump_to_sqlite(dump_path, out_path)
    print(
        f"Loaded: gcd_publisher={counts['gcd_publisher']:,}  "
        f"gcd_series={counts['gcd_series']:,}  gcd_issue={counts['gcd_issue']:,}"
    )

    if args.no_run:
        print("--no-run set; skipping dry-run. Run it later with:")
        print(f"  python scripts/gcd_barcode_backfill.py --gcd-db {out_path} --limit {args.limit} --resume {DEFAULT_RESUME}")
        return

    DEFAULT_RESUME.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "scripts/gcd_barcode_backfill.py",
        "--gcd-db",
        str(out_path),
        "--limit",
        str(args.limit),
        "--resume",
        str(DEFAULT_RESUME),
    ]
    print(f"\nRunning dry-run: {' '.join(cmd)}\n")
    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()
