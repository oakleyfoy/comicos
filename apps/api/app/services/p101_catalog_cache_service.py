"""Local SQLite cache of ComicOS catalog issues for offline GCD comparison."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import extract, func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.intake_queue import ComicIssueBarcode
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    series_names_compatible,
)
from app.services.p101_modern_catalog_audit_service import issue_year_key

DEFAULT_CACHE_PATH = Path("data/p101/comicos_catalog_cache.sqlite")
YEAR_MIN = 2009
YEAR_MAX = 2026

_SCHEMA = """
CREATE TABLE catalog_issue_cache (
  issue_id INTEGER PRIMARY KEY,
  publisher_norm TEXT NOT NULL,
  series_norm TEXT NOT NULL,
  issue_norm TEXT NOT NULL,
  year INTEGER,
  publisher_name TEXT,
  series_name TEXT,
  issue_number TEXT
);
CREATE INDEX IF NOT EXISTS ix_cache_key ON catalog_issue_cache(publisher_norm, series_norm, issue_norm);
CREATE INDEX IF NOT EXISTS ix_cache_series_issue ON catalog_issue_cache(series_norm, issue_norm);
CREATE INDEX IF NOT EXISTS ix_cache_year ON catalog_issue_cache(year);
CREATE TABLE catalog_upc_cache (
  normalized_upc TEXT PRIMARY KEY,
  issue_id INTEGER NOT NULL
);
CREATE TABLE learned_barcode_cache (
  normalized_barcode TEXT PRIMARY KEY
);
"""


def export_catalog_cache(session: Session, cache_path: Path) -> int:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        cache_path.unlink()

    conn = sqlite3.connect(cache_path)
    conn.executescript(_SCHEMA)
    conn.execute("PRAGMA synchronous=OFF")

    pubs = {int(pid): name for pid, name in session.exec(select(CatalogPublisher.id, CatalogPublisher.name)).all() if pid}
    series_rows = session.exec(
        select(CatalogSeries.id, CatalogSeries.name, CatalogSeries.publisher_id, CatalogSeries.start_year)
    ).all()
    series_meta = {
        int(sid): (name, pub_id, start_year)
        for sid, name, pub_id, start_year in series_rows
        if sid is not None
    }

    batch: list[tuple] = []
    rows = session.exec(
        select(
            CatalogIssue.id,
            CatalogIssue.series_id,
            CatalogIssue.publisher_id,
            CatalogIssue.issue_number,
            CatalogIssue.normalized_issue_number,
            CatalogIssue.cover_date,
            CatalogIssue.release_date,
        )
    ).all()

    for issue_id, series_id, publisher_id, issue_number, norm_issue, cover_date, release_date in rows:
        if issue_id is None or series_id is None:
            continue
        series_name, _spub, start_year = series_meta.get(int(series_id), ("", None, None))
        pub_name = pubs.get(int(publisher_id or 0), "") if publisher_id else ""
        pub_norm = normalize_series_name(pub_name)
        ser_norm = normalize_series_name(series_name)
        iss_norm = normalize_issue_number(norm_issue or issue_number or "")
        if not pub_norm or not ser_norm or not iss_norm:
            continue
        year = issue_year_key(
            cover_date.year if cover_date is not None else None,
            release_date.year if release_date is not None else (int(start_year) if start_year else None),
        )
        year_int = int(year) if isinstance(year, int) else None
        batch.append(
            (
                int(issue_id),
                pub_norm,
                ser_norm,
                iss_norm,
                year_int,
                pub_name,
                series_name,
                issue_number or "",
            )
        )
        if len(batch) >= 5000:
            conn.executemany(
                """
                INSERT INTO catalog_issue_cache
                (issue_id, publisher_norm, series_norm, issue_norm, year, publisher_name, series_name, issue_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            batch = []
    if batch:
        conn.executemany(
            """
            INSERT INTO catalog_issue_cache
            (issue_id, publisher_norm, series_norm, issue_norm, year, publisher_name, series_name, issue_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )
    conn.commit()

    upc_batch: list[tuple] = []
    for upc, issue_id in session.exec(select(CatalogUpc.normalized_upc, CatalogUpc.issue_id)).all():
        if upc and issue_id is not None:
            upc_batch.append((str(upc), int(issue_id)))
        if len(upc_batch) >= 5000:
            conn.executemany("INSERT OR IGNORE INTO catalog_upc_cache VALUES (?, ?)", upc_batch)
            upc_batch = []
    if upc_batch:
        conn.executemany("INSERT OR IGNORE INTO catalog_upc_cache VALUES (?, ?)", upc_batch)

    learned_batch: list[tuple] = []
    for (bc,) in session.exec(select(ComicIssueBarcode.normalized_barcode)).all():
        if bc:
            learned_batch.append((str(bc),))
        if len(learned_batch) >= 5000:
            conn.executemany("INSERT OR IGNORE INTO learned_barcode_cache VALUES (?)", learned_batch)
            learned_batch = []
    if learned_batch:
        conn.executemany("INSERT OR IGNORE INTO learned_barcode_cache VALUES (?)", learned_batch)

    conn.commit()
    count = int(conn.execute("SELECT COUNT(*) FROM catalog_issue_cache").fetchone()[0])
    conn.close()
    return count


@dataclass
class CatalogCacheMatcher:
    exact_keys: set[tuple[str, str, str]]
    by_series_issue: dict[tuple[str, str], list[tuple[str, int | None]]]

    @classmethod
    def from_sqlite(cls, cache_path: Path) -> "CatalogCacheMatcher":
        conn = sqlite3.connect(cache_path)
        exact: set[tuple[str, str, str]] = set()
        by_si: dict[tuple[str, str], list[tuple[str, int | None]]] = {}
        for pub, ser, iss, year in conn.execute(
            "SELECT publisher_norm, series_norm, issue_norm, year FROM catalog_issue_cache"
        ):
            exact.add((str(pub), str(ser), str(iss)))
            key = (str(ser), str(iss))
            by_si.setdefault(key, []).append((str(pub), int(year) if year is not None else None))
        conn.close()
        return cls(exact_keys=exact, by_series_issue=by_si)

    def matches(self, *, publisher: str, series: str, issue_number: str, year: int | None) -> bool:
        pub_norm = normalize_series_name(publisher)
        ser_norm = normalize_series_name(series)
        iss_norm = normalize_issue_number(issue_number)
        if not pub_norm or not ser_norm or not iss_norm:
            return False
        if (pub_norm, ser_norm, iss_norm) in self.exact_keys:
            return True
        candidates = self.by_series_issue.get((ser_norm, iss_norm))
        if not candidates:
            return False
        if len(candidates) == 1:
            return True
        pub_matches = [c for c in candidates if c[0] == pub_norm or series_names_compatible(pub_norm, c[0])]
        if len(pub_matches) == 1:
            return True
        if not pub_matches or year is None:
            return False
        scored = sorted(
            pub_matches,
            key=lambda c: abs((c[1] if c[1] is not None else year) - year),
        )
        if len(scored) >= 2 and abs((scored[0][1] or year) - year) == abs((scored[1][1] or year) - year):
            return False
        return True


def comicos_counts_by_year(cache_path: Path) -> dict[int, int]:
    conn = sqlite3.connect(cache_path)
    rows = conn.execute(
        """
        SELECT year, COUNT(*) FROM catalog_issue_cache
        WHERE year BETWEEN ? AND ?
        GROUP BY year ORDER BY year
        """,
        (YEAR_MIN, YEAR_MAX),
    ).fetchall()
    conn.close()
    return {int(y): int(c) for y, c in rows if y is not None}


@dataclass
class CatalogCacheContext:
    matcher: CatalogCacheMatcher
    upc_to_issue: dict[str, int]
    learned_barcodes: set[str]

    @classmethod
    def load(cls, cache_path: Path) -> "CatalogCacheContext":
        conn = sqlite3.connect(cache_path)
        upc_to_issue = {
            str(upc): int(iid)
            for upc, iid in conn.execute("SELECT normalized_upc, issue_id FROM catalog_upc_cache")
        }
        learned = {str(r[0]) for r in conn.execute("SELECT normalized_barcode FROM learned_barcode_cache")}
        conn.close()
        return cls(
            matcher=CatalogCacheMatcher.from_sqlite(cache_path),
            upc_to_issue=upc_to_issue,
            learned_barcodes=learned,
        )
