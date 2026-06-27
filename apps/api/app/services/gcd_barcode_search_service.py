"""Deep search of GCD SQLite for barcodes (barcode, notes, isbn fields)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.services.barcode_validation_service import base_upc, supplement_extension
from app.services.catalog_ingestion_service import normalize_upc
from app.services.gcd_barcode_import_service import extract_barcodes

GcdHitField = Literal["barcode", "notes", "isbn"]
GcdHitKind = Literal["exact", "prefix"]


@dataclass
class GcdBarcodeFieldHit:
    gcd_issue_id: int
    publisher: str | None
    series: str | None
    issue_number: str | None
    kind: GcdHitKind
    source_field: GcdHitField
    raw_value: str | None
    extracted_barcodes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "gcd_issue_id": self.gcd_issue_id,
            "publisher": self.publisher,
            "series": self.series,
            "issue_number": self.issue_number,
            "kind": self.kind,
            "source_field": self.source_field,
            "raw_value": self.raw_value,
            "extracted_barcodes": self.extracted_barcodes,
        }


@dataclass
class GcdBarcodeSearchReport:
    searched_full_barcode: str
    searched_upc12: str
    searched_supplement: str
    gcd_exact_hits: list[GcdBarcodeFieldHit] = field(default_factory=list)
    gcd_prefix_hits: list[GcdBarcodeFieldHit] = field(default_factory=list)
    gcd_notes_hits: list[GcdBarcodeFieldHit] = field(default_factory=list)
    final_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "searched_full_barcode": self.searched_full_barcode,
            "searched_upc12": self.searched_upc12,
            "searched_supplement": self.searched_supplement,
            "gcd_exact_hits": [h.to_dict() for h in self.gcd_exact_hits],
            "gcd_prefix_hits": [h.to_dict() for h in self.gcd_prefix_hits],
            "gcd_notes_hits": [h.to_dict() for h in self.gcd_notes_hits],
            "final_reason": self.final_reason,
        }


def _search_patterns(normalized: str) -> tuple[str, str, str]:
    full = normalized
    upc12 = base_upc(full) if len(full) >= 12 else full
    supp = supplement_extension(full) if len(full) >= 17 else ""
    return full, upc12, supp


def _classify_row_hits(
    *,
    normalized: str,
    upc12: str,
    row: tuple,
) -> list[GcdBarcodeFieldHit]:
    gcd_issue_id = int(row[0])
    publisher = row[1]
    series = row[2]
    issue_number = row[3]
    hits: list[GcdBarcodeFieldHit] = []

    for field_name, raw in (
        ("barcode", row[4]),
        ("notes", row[5]),
        ("isbn", row[6]),
    ):
        if raw is None or not str(raw).strip():
            continue
        text = str(raw)
        extracted = extract_barcodes(text)
        if normalized in extracted:
            hits.append(
                GcdBarcodeFieldHit(
                    gcd_issue_id=gcd_issue_id,
                    publisher=publisher,
                    series=series,
                    issue_number=issue_number,
                    kind="exact",
                    source_field=field_name,  # type: ignore[arg-type]
                    raw_value=text[:500],
                    extracted_barcodes=extracted,
                )
            )
            continue
        prefix = any(
            ext == upc12
            or (len(normalized) >= 17 and ext.startswith(upc12) and len(ext) < len(normalized))
            for ext in extracted
        )
        if prefix:
            hits.append(
                GcdBarcodeFieldHit(
                    gcd_issue_id=gcd_issue_id,
                    publisher=publisher,
                    series=series,
                    issue_number=issue_number,
                    kind="prefix",
                    source_field=field_name,  # type: ignore[arg-type]
                    raw_value=text[:500],
                    extracted_barcodes=extracted,
                )
            )
            continue
        flat = normalize_upc(text)
        if normalized and normalized in flat:
            hits.append(
                GcdBarcodeFieldHit(
                    gcd_issue_id=gcd_issue_id,
                    publisher=publisher,
                    series=series,
                    issue_number=issue_number,
                    kind="exact",
                    source_field=field_name,  # type: ignore[arg-type]
                    raw_value=text[:500],
                    extracted_barcodes=extracted,
                )
            )
        elif upc12 and len(upc12) >= 12 and upc12 in flat:
            hits.append(
                GcdBarcodeFieldHit(
                    gcd_issue_id=gcd_issue_id,
                    publisher=publisher,
                    series=series,
                    issue_number=issue_number,
                    kind="prefix",
                    source_field=field_name,  # type: ignore[arg-type]
                    raw_value=text[:500],
                    extracted_barcodes=extracted,
                )
            )
    return hits


def _gcd_issue_text_columns(gcd_path: Path) -> tuple[str, ...]:
    conn = sqlite3.connect(gcd_path)
    cols = {c[1] for c in conn.execute("PRAGMA table_info(gcd_issue)").fetchall()}
    conn.close()
    out: list[str] = []
    for name in ("barcode", "notes", "isbn"):
        if name in cols:
            out.append(name)
    return tuple(out) if out else ("barcode",)


def search_gcd_barcode_fields(gcd_path: Path, scanned_barcode: str) -> GcdBarcodeSearchReport:
    normalized = normalize_upc(scanned_barcode) or scanned_barcode.strip()
    full, upc12, supp = _search_patterns(normalized)
    report = GcdBarcodeSearchReport(
        searched_full_barcode=full,
        searched_upc12=upc12,
        searched_supplement=supp,
    )
    if not gcd_path.is_file() or len(normalized) < 8:
        report.final_reason = "gcd_database_missing_or_invalid_barcode"
        return report

    like_terms = [t for t in (full, upc12) if t and len(t) >= 8]
    if supp and len(supp) == 5 and upc12:
        like_terms.append(upc12 + supp)
    like_terms = list(dict.fromkeys(like_terms))

    text_cols = _gcd_issue_text_columns(gcd_path)
    select_cols = ", ".join(f"i.{c}" for c in text_cols)
    # Row layout: id, pub, series, number, then text cols..., key_date, year_began, title
    issue_select = f"""
    SELECT i.id, p.name, s.name, i.number, {select_cols},
           i.key_date, s.year_began, i.title
    FROM gcd_issue i
    JOIN gcd_series s ON s.id = i.series_id
    LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
    WHERE {{where_sql}}
    """

    clauses: list[str] = []
    params: list[str] = []
    for term in like_terms:
        for col in text_cols:
            clauses.append(f"(i.{col} IS NOT NULL AND TRIM(i.{col}) <> '' AND i.{col} LIKE ?)")
            params.append(f"%{term}%")

    if not clauses:
        report.final_reason = "no_gcd_barcode_match"
        return report

    where_sql = " OR ".join(clauses)
    conn = sqlite3.connect(gcd_path)
    conn.execute("PRAGMA query_only = ON")
    cur = conn.execute(issue_select.format(where_sql=where_sql), tuple(params))

    exact_by_id: dict[int, GcdBarcodeFieldHit] = {}
    prefix_by_id: dict[int, GcdBarcodeFieldHit] = {}
    notes_by_id: dict[int, GcdBarcodeFieldHit] = {}

    col_index = {name: 4 + idx for idx, name in enumerate(text_cols)}

    while True:
        batch = cur.fetchmany(500)
        if not batch:
            break
        for row in batch:
            field_values = {name: row[col_index[name]] for name in text_cols}
            pseudo_row = (
                row[0],
                row[1],
                row[2],
                row[3],
                field_values.get("barcode"),
                field_values.get("notes"),
                field_values.get("isbn"),
            )
            for hit in _classify_row_hits(normalized=normalized, upc12=upc12, row=pseudo_row):
                bucket = exact_by_id if hit.kind == "exact" else prefix_by_id
                if hit.gcd_issue_id not in bucket:
                    bucket[hit.gcd_issue_id] = hit
                if hit.source_field == "notes" and hit.gcd_issue_id not in notes_by_id:
                    notes_by_id[hit.gcd_issue_id] = hit

    conn.close()

    report.gcd_exact_hits = list(exact_by_id.values())
    report.gcd_prefix_hits = [h for i, h in prefix_by_id.items() if i not in exact_by_id]
    report.gcd_notes_hits = list(notes_by_id.values())

    if report.gcd_exact_hits:
        report.final_reason = "gcd_exact_barcode_match"
    elif report.gcd_prefix_hits or report.gcd_notes_hits:
        report.final_reason = "gcd_prefix_or_partial_match_only"
    else:
        report.final_reason = "no_gcd_barcode_match"
    return report


def find_gcd_rows_by_normalized_barcode(gcd_path: Path, normalized: str) -> list[dict[str, Any]]:
    """Issues whose barcode/notes/isbn extract to an exact normalized barcode match."""
    report = search_gcd_barcode_fields(gcd_path, normalized)
    matches: list[dict[str, Any]] = []
    for hit in report.gcd_exact_hits:
        matches.append(
            {
                "gcd_issue_id": hit.gcd_issue_id,
                "publisher": hit.publisher,
                "series": hit.series,
                "issue_number": hit.issue_number,
                "barcode_raw": hit.raw_value if hit.source_field == "barcode" else None,
                "match_source_field": hit.source_field,
                "extracted_barcodes": hit.extracted_barcodes,
            }
        )
    # Enrich with key_date from DB when needed for downstream
    if matches:
        conn = sqlite3.connect(gcd_path)
        for m in matches:
            row = conn.execute(
                """
                SELECT i.barcode, i.key_date, s.year_began, i.title
                FROM gcd_issue i JOIN gcd_series s ON s.id = i.series_id WHERE i.id = ?
                """,
                (int(m["gcd_issue_id"]),),
            ).fetchone()
            if row:
                m["barcode_raw"] = m.get("barcode_raw") or row[0]
                m["key_date"] = row[1]
                m["year_began"] = row[2]
                m["title"] = row[3]
        conn.close()
    return matches
