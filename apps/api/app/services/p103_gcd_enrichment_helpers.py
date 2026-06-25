"""Shared helpers for P103 GCD catalog enrichment (update-only)."""

from __future__ import annotations

import re
import sqlite3
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    normalize_upc,
    series_names_compatible,
)
from app.services.gcd_barcode_import_service import GCD_SOURCE, extract_barcodes, _year_from_key_date
from app.services.p102_gcd_modern_acquisition_service import _REPRINT_DIGEST, _VARIANT

_GCD_ID_RE = re.compile(r"^\d+$")


def extract_gcd_issue_id(external_source_ids: dict | None) -> int | None:
    if not isinstance(external_source_ids, dict):
        return None
    bucket = external_source_ids.get(GCD_SOURCE)
    if isinstance(bucket, dict):
        for key in bucket:
            if _GCD_ID_RE.match(str(key)):
                return int(key)
    return None


def parse_key_date(key_date: str | None, fallback_year: int | None) -> tuple[date | None, int | None, int | None]:
    """Return (calendar_date, year, month) from GCD key_date YYYY-MM-DD."""
    text = str(key_date or "").strip()
    if len(text) >= 7 and text[4] == "-":
        try:
            y = int(text[0:4])
            m = int(text[5:7])
            d = int(text[8:10]) if len(text) >= 10 and text[8:10].isdigit() else 1
            if m == 0:
                m = 1
            if d == 0:
                d = 1
            return date(y, m, d), y, m
        except (TypeError, ValueError):
            pass
    if fallback_year is not None:
        return date(int(fallback_year), 1, 1), int(fallback_year), None
    return None, None, None


def classify_variant_label(series: str, issue_number: str, notes: str | None = None) -> str | None:
    blob = f"{series} {issue_number} {notes or ''}"
    if _VARIANT.search(blob):
        m = re.search(r"\bCover\s+([A-Z0-9]+)\b", blob, re.I)
        if m:
            return f"Cover {m.group(1).upper()}"
        if re.search(r"\bvirgin\b", blob, re.I):
            return "Virgin"
        if re.search(r"\bfoil\b", blob, re.I):
            return "Foil"
        if re.search(r"\bsketch\b", blob, re.I):
            return "Sketch"
        if re.search(r"\bblank\b", blob, re.I):
            return "Blank"
        if re.search(r"\bincentive\b", blob, re.I):
            return "Incentive"
        if re.search(r"\bconnecting\b", blob, re.I):
            return "Connecting"
        if re.search(r"\bratio\b", blob, re.I):
            return "Ratio"
        return "Variant"
    return None


def classify_printing_label(series: str, issue_number: str, notes: str | None = None) -> str | None:
    blob = f"{series} {issue_number} {notes or ''}"
    if _REPRINT_DIGEST.search(blob):
        for label in (
            "Director's Cut",
            "Second Printing",
            "Third Printing",
            "First Printing",
            "Facsimile",
            "Reprint",
        ):
            if label.lower().replace("'", "") in blob.lower().replace("'", ""):
                return label
        if re.search(r"second\s+print", blob, re.I):
            return "Second Printing"
        if re.search(r"third\s+print", blob, re.I):
            return "Third Printing"
        return "Reprint"
    return None


def resolve_catalog_issue_id_from_cache(
    cache_path: Any,
    *,
    publisher: str,
    series: str,
    issue_number: str,
) -> int | None:
    path = str(cache_path)
    pub_norm = normalize_series_name(publisher)
    ser_norm = normalize_series_name(series)
    iss_norm = normalize_issue_number(issue_number)
    if not pub_norm or not ser_norm or not iss_norm:
        return None
    conn = sqlite3.connect(path)
    row = conn.execute(
        """
        SELECT issue_id FROM catalog_issue_cache
        WHERE publisher_norm = ? AND series_norm = ? AND issue_norm = ?
        LIMIT 1
        """,
        (pub_norm, ser_norm, iss_norm),
    ).fetchone()
    conn.close()
    return int(row[0]) if row else None


def resolve_catalog_issue_id_for_gcd_match(
    cache_path: Any,
    *,
    publisher: str,
    series: str,
    issue_number: str,
) -> int | None:
    """Resolve catalog issue when GCD cache matcher agrees (exact pub or unique series+issue)."""
    exact = resolve_catalog_issue_id_from_cache(
        cache_path,
        publisher=publisher,
        series=series,
        issue_number=issue_number,
    )
    if exact is not None:
        return exact
    ser_norm = normalize_series_name(series)
    iss_norm = normalize_issue_number(issue_number)
    pub_norm = normalize_series_name(publisher)
    if not ser_norm or not iss_norm:
        return None
    path = str(cache_path)
    conn = sqlite3.connect(path)
    rows = conn.execute(
        """
        SELECT issue_id, publisher_norm FROM catalog_issue_cache
        WHERE series_norm = ? AND issue_norm = ?
        """,
        (ser_norm, iss_norm),
    ).fetchall()
    conn.close()
    if not rows:
        return None
    if len(rows) == 1:
        return int(rows[0][0])
    pub_matches = [r for r in rows if r[1] == pub_norm or series_names_compatible(str(r[1]), pub_norm)]
    if len(pub_matches) == 1:
        return int(pub_matches[0][0])
    return None


def gcd_row_to_plan_inputs(row: dict[str, Any]) -> dict[str, Any]:
    year = _year_from_key_date(row.get("key_date"), row.get("year_began"))
    barcodes = extract_barcodes(row.get("barcode"))
    barcode = barcodes[0] if barcodes else None
    series = str(row.get("series_name") or "")
    number = str(row.get("number") or "")
    notes = str(row.get("notes") or "") if row.get("notes") else None
    return {
        "gcd_issue_id": int(row["issue_id"]),
        "gcd_series_id": int(row["gcd_series_id"]) if row.get("gcd_series_id") is not None else None,
        "gcd_publisher_id": int(row["gcd_publisher_id"]) if row.get("gcd_publisher_id") is not None else None,
        "publisher": str(row.get("publisher_name") or ""),
        "series": series,
        "issue_number": number,
        "key_date": row.get("key_date"),
        "year": int(year) if year is not None else None,
        "barcode": barcode,
        "title": str(row.get("title") or "").strip() or None,
        "notes": notes,
        "variant_label": classify_variant_label(series, number, notes),
        "printing_label": classify_printing_label(series, number, notes),
        "calendar_date": parse_key_date(str(row.get("key_date") or ""), year)[0],
    }


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def normalized_upc_taken(session, normalized: str, issue_id: int) -> bool:
    from sqlmodel import select

    from app.models.catalog_master import CatalogUpc

    existing = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if existing is None:
        return False
    return int(existing.issue_id or 0) != int(issue_id)
