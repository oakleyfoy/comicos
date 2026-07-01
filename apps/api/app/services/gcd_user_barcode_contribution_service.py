"""Write user-confirmed barcode + identity rows into the local GCD SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from app.services.barcode_scan_consensus_service import normalize_scan_preserving_supplement
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    series_names_compatible,
)
from app.services.p106_1_gcd_non_barcode_recovery_service import _issue_number_sql_variants

USER_GCD_ID_FLOOR = 9_000_000_000
_COMICOS_NOTE_PREFIX = "ComicOS cover-read contribution"


def _next_table_id(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT MAX(id) FROM {table}").fetchone()
    max_id = int(row[0] or 0)
    if max_id < USER_GCD_ID_FLOOR:
        return USER_GCD_ID_FLOOR
    return max_id + 1


def _publisher_matches(hint: str | None, candidate: str | None) -> bool:
    if not hint or not candidate:
        return bool(not hint)
    a = normalize_series_name(hint)
    b = normalize_series_name(candidate)
    if a == b:
        return True
    return series_names_compatible(a, b)


def find_gcd_issue_by_identity(
    gcd_path: Path,
    *,
    series: str,
    issue_number: str,
    publisher: str | None = None,
) -> dict[str, Any] | None:
    """Best GCD issue row for a cover-read identity (series + issue + optional publisher)."""
    if not gcd_path.is_file():
        return None
    issue_norm = normalize_issue_number(str(issue_number or ""))
    variants = _issue_number_sql_variants(issue_number)
    if not issue_norm or not variants:
        return None
    series_norm = normalize_series_name(series)
    if not series_norm:
        return None
    placeholders = ", ".join("?" * len(variants))
    sql = f"""
        SELECT i.id AS gcd_issue_id,
               p.name AS publisher,
               s.name AS series,
               i.number AS issue_number,
               i.barcode AS barcode_raw,
               i.title AS title,
               i.notes AS notes
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE trim(i.number) IN ({placeholders})
        """
    conn = sqlite3.connect(gcd_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, tuple(variants)).fetchall()
    finally:
        conn.close()

    matches: list[dict[str, Any]] = []
    for row in rows:
        if normalize_issue_number(str(row["issue_number"] or "")) != issue_norm:
            continue
        cand_series = normalize_series_name(str(row["series"] or ""))
        if cand_series != series_norm and not series_names_compatible(cand_series, series_norm):
            continue
        if publisher and not _publisher_matches(publisher, str(row["publisher"] or "")):
            continue
        matches.append(dict(row))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # Prefer an existing facsimile/reprint note, else first row.
    for row in matches:
        blob = f"{row.get('notes') or ''} {row.get('title') or ''}".lower()
        if "facsimile" in blob or "reprint" in blob:
            return row
    return matches[0]


def contribute_barcode_to_gcd(
    gcd_path: Path,
    *,
    series: str,
    issue_number: str,
    publisher: str | None,
    barcode: str,
    title: str | None = None,
    year: int | None = None,
    facsimile: bool = False,
    intake_item_id: int | None = None,
) -> int:
    """Attach ``barcode`` to an existing GCD issue or insert a user-contributed row.

    Returns the ``gcd_issue_id`` used for catalog import / future barcode scans.
    """
    if not gcd_path.is_file():
        raise FileNotFoundError(f"GCD database not found: {gcd_path}")
    normalized = normalize_scan_preserving_supplement(barcode) or barcode.strip()
    if not normalized:
        raise ValueError("barcode required")

    existing = find_gcd_issue_by_identity(
        gcd_path,
        series=series,
        issue_number=issue_number,
        publisher=publisher,
    )

    note_bits = [_COMICOS_NOTE_PREFIX, f"barcode={normalized}"]
    if facsimile:
        note_bits.append("facsimile_or_reprint")
    if intake_item_id is not None:
        note_bits.append(f"intake_item_id={intake_item_id}")
    contribution_note = "; ".join(note_bits)

    conn = sqlite3.connect(gcd_path)
    try:
        if existing is not None:
            gcd_issue_id = int(existing["gcd_issue_id"])
            prior_notes = str(existing.get("notes") or "").strip()
            merged_notes = f"{prior_notes}\n{contribution_note}".strip() if prior_notes else contribution_note
            conn.execute(
                "UPDATE gcd_issue SET barcode = ?, notes = ? WHERE id = ?",
                (normalized, merged_notes, gcd_issue_id),
            )
            conn.commit()
            return gcd_issue_id

        pub_name = (publisher or "Unknown").strip() or "Unknown"
        pub_id = conn.execute(
            "SELECT id FROM gcd_publisher WHERE lower(trim(name)) = lower(trim(?)) LIMIT 1",
            (pub_name,),
        ).fetchone()
        if pub_id is None:
            pub_id_val = _next_table_id(conn, "gcd_publisher")
            conn.execute(
                "INSERT INTO gcd_publisher (id, name) VALUES (?, ?)",
                (pub_id_val, pub_name),
            )
        else:
            pub_id_val = int(pub_id[0])

        series_name = series.strip() or "Unknown"
        series_id = conn.execute(
            """
            SELECT id FROM gcd_series
            WHERE publisher_id = ? AND lower(trim(name)) = lower(trim(?))
            LIMIT 1
            """,
            (pub_id_val, series_name),
        ).fetchone()
        if series_id is None:
            series_id_val = _next_table_id(conn, "gcd_series")
            conn.execute(
                "INSERT INTO gcd_series (id, name, year_began, publisher_id) VALUES (?, ?, ?, ?)",
                (series_id_val, series_name, year, pub_id_val),
            )
        else:
            series_id_val = int(series_id[0])

        issue_id_val = _next_table_id(conn, "gcd_issue")
        key_date = f"{year}-01-00" if year else None
        conn.execute(
            """
            INSERT INTO gcd_issue (id, number, barcode, key_date, series_id, title, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                issue_id_val,
                str(issue_number).strip(),
                normalized,
                key_date,
                series_id_val,
                (title or series_name).strip() or series_name,
                contribution_note,
            ),
        )
        conn.commit()
        return int(issue_id_val)
    finally:
        conn.close()
