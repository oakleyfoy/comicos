"""Scanner barcode authority: partial UPC, P106/GCD over OCR/fingerprint, decode sanity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.catalog_ingestion_service import merge_comic_upc_decodes, normalize_upc
from app.services.gcd_barcode_search_service import find_gcd_rows_by_normalized_barcode
from app.services.p105_comic_barcode_read_service import ComicBarcodeReadResult
from app.services.p106_barcode_gap_resolver_service import (
    _gcd_display_issue_number,
    _gcd_display_publisher,
    _gcd_display_series,
)

PARTIAL_BARCODE_REASON = "Couldn't read full barcode — rescan with supplement visible."
DECODE_DISAGREEMENT_REASON = "Barcode decode disagreement — rescan with the full UPC and supplement visible."
LOW_CONFIDENCE_DECODE_REASON = (
    "Barcode read confidence is low and GCD has no exact match — rescan before importing."
)


def _five_digit_supplement(value: str | None) -> str:
    digits = normalize_upc(value or "")
    return digits if len(digits) == 5 else ""


def try_resolve_seventeen_digit_barcode_from_p105(*, normalized: str, p105: ComicBarcodeReadResult) -> str | None:
    """Merge 12-digit main UPC with any recovered 5-digit supplement from P105."""
    digits = normalize_upc(normalized)
    if len(digits) >= 17:
        return digits[:17]
    main = normalize_upc(p105.main_upc or digits)
    if len(main) != 12:
        return None
    supplements: list[str] = []
    for raw in (
        p105.final_supplement,
        p105.decoded_supplement,
        p105.ocr_supplement,
        p105.left_supplement_ocr,
        p105.corrected_supplement,
    ):
        sup = _five_digit_supplement(raw)
        if sup:
            supplements.append(sup)
    unique = list(dict.fromkeys(supplements))
    if len(unique) == 1:
        merged = merge_comic_upc_decodes([main, unique[0]])
        if merged and len(normalize_upc(merged)) >= 17:
            return normalize_upc(merged)[:17]
    recon = normalize_upc(p105.reconstructed_full or "")
    if len(recon) >= 17:
        return recon[:17]
    return None


def comic_barcode_scan_is_partial(*, normalized: str, p105: ComicBarcodeReadResult) -> bool:
    """True when only a 12-digit body was captured (no reliable 17-digit UPC+5)."""
    digits = normalize_upc(normalized)
    if len(digits) >= 17:
        return False
    if len(digits) != 12:
        return False
    recon = normalize_upc(p105.reconstructed_full or "")
    return len(recon) < 17


def mark_partial_barcode_in_read_json(barcode_read_json: str | None) -> str:
    payload: dict[str, Any] = {}
    if barcode_read_json:
        try:
            parsed = json.loads(barcode_read_json)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = {}
    payload["partial_barcode"] = True
    payload["partial_barcode_reason"] = PARTIAL_BARCODE_REASON
    return json.dumps(payload)


def p106_gap_is_exact_barcode_authority(gap_diag: dict[str, Any] | None) -> bool:
    if not gap_diag:
        return False
    if int(gap_diag.get("gcd_match_count") or 0) != 1:
        return False
    return bool(gap_diag.get("exact_barcode_path"))


def sync_intake_display_from_p106_gap(item: Any, gap_diag: dict[str, Any]) -> None:
    """P106 exact barcode identity overrides OCR/title display fields."""
    if not p106_gap_is_exact_barcode_authority(gap_diag):
        return
    series = _gcd_display_series(gap_diag)
    issue_number = _gcd_display_issue_number(gap_diag)
    publisher = _gcd_display_publisher(gap_diag)
    if series:
        item.matched_series = series
    if issue_number:
        item.matched_issue_number = issue_number
    if publisher:
        item.matched_publisher = publisher
    matches = gap_diag.get("gcd_matches") or []
    if matches and isinstance(matches[0], dict):
        yb = matches[0].get("year_began")
        if yb is not None and not (getattr(item, "matched_year", None) or "").strip():
            item.matched_year = str(yb)


def find_unique_gcd_one_digit_barcode_variant(gcd_path: Path, normalized: str) -> str | None:
    """If no exact GCD hit, detect a unique one-digit UPC-A correction that exact-matches GCD."""
    import sqlite3

    digits = normalize_upc(normalized)
    if len(digits) < 17 or not gcd_path.is_file():
        return None
    if find_gcd_rows_by_normalized_barcode(gcd_path, digits):
        return None
    conn = sqlite3.connect(gcd_path)
    try:
        found: list[str] = []
        body = list(digits[:12])
        suffix = digits[12:17]
        for idx in range(12):
            orig = body[idx]
            for d in "0123456789":
                if d == orig:
                    continue
                trial = "".join(body[:idx] + [d] + body[idx + 1 :]) + suffix
                row = conn.execute(
                    "SELECT id FROM gcd_issue WHERE barcode = ? LIMIT 1",
                    (trial,),
                ).fetchone()
                if row:
                    found.append(trial)
        unique = list(dict.fromkeys(found))
        if len(unique) == 1:
            return unique[0]
        return None
    finally:
        conn.close()


def barcode_decode_review_reason(
    *,
    p105: ComicBarcodeReadResult,
    normalized: str,
    gcd_path: Path | None,
) -> str | None:
    if p105.supplement_disagreement:
        return DECODE_DISAGREEMENT_REASON
    if p105.inferred_supplement and (p105.supplement_decode_confidence or 0) < 0.85:
        return p105.review_reason or "Inferred supplement digits — rescan to confirm."
    digits = normalize_upc(normalized)
    if len(digits) >= 17 and gcd_path is not None and gcd_path.is_file():
        if not find_gcd_rows_by_normalized_barcode(gcd_path, digits):
            alt = find_unique_gcd_one_digit_barcode_variant(gcd_path, digits)
            if alt:
                return (
                    f"Barcode not in GCD; similar barcode {alt} is an exact GCD match — "
                    "likely misread, rescan."
                )
            if (p105.confidence_main or 0) < 0.88 and (p105.confidence_reconstructed or 0) < 0.88:
                return LOW_CONFIDENCE_DECODE_REASON
    return None


def p105_field_test_snapshot(p105: ComicBarcodeReadResult) -> dict[str, Any]:
    return {
        "raw_decoded_barcode": p105.raw_decoded_barcode,
        "main_upc": p105.main_upc,
        "reconstructed_full": p105.reconstructed_full,
        "final_supplement": p105.final_supplement,
        "supplement_disagreement": p105.supplement_disagreement,
        "inferred_supplement": p105.inferred_supplement,
        "supplement_decode_confidence": p105.supplement_decode_confidence,
        "confidence_main": p105.confidence_main,
        "confidence_reconstructed": p105.confidence_reconstructed,
        "ocr_supplement": p105.ocr_supplement,
        "left_supplement_ocr": p105.left_supplement_ocr,
        "fingerprint_confirmed": p105.fingerprint_confirmed,
        "catalog_confirmed": p105.catalog_confirmed,
        "supplement_candidates": p105.supplement_candidates[:5],
        "review_reason": p105.review_reason,
    }
