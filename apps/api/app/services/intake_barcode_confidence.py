"""Intake scanner confidence: when full UPC+5 + local catalog wins over OCR noise."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.models.catalog_master import CatalogUpc
from app.models.intake_queue import (
    MATCH_SOURCE_CATALOG_UPC,
    MATCH_SOURCE_LEARNED,
    ComicIssueBarcode,
)
from app.services.barcode_validation_service import (
    barcode_encoded_issue_number,
    parse_comic_upc_extension,
    supplement_extension,
)
from app.services.catalog_ingestion_service import (
    comic_barcode_lookup_keys_for_search,
    direct_market_requires_supplement_key,
    normalize_upc,
)
from app.services.photo_import_fingerprint_service import (
    fingerprint_match_score_for_crop_path,
    search_catalog_fingerprint_hits_for_crop_path,
)

LOCAL_TRUSTED_MATCH_SOURCES = frozenset({MATCH_SOURCE_LEARNED, MATCH_SOURCE_CATALOG_UPC})

# Cover must strongly point at a *different* issue before we block a local barcode match.
_COVER_CONTRADICT_THRESHOLD = 0.75


def has_full_direct_market_barcode(normalized: str) -> bool:
    digits = normalize_upc(normalized)
    return len(digits) >= 17 and not direct_market_requires_supplement_key(digits)


def is_local_trusted_match_source(source: str | None) -> bool:
    return (source or "") in LOCAL_TRUSTED_MATCH_SOURCES


def distinct_catalog_issue_ids_for_barcode(session: Session, barcode: str) -> set[int]:
    """Distinct catalog issue ids tied to this barcode via catalog_upc keys (+ learned row)."""
    ids: set[int] = set()
    for key in comic_barcode_lookup_keys_for_search(barcode):
        if len(key) < 17 and direct_market_requires_supplement_key(barcode):
            continue
        rows = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == key)).all()
        for row in rows:
            if row.issue_id is not None:
                ids.add(int(row.issue_id))
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == normalize_upc(barcode))
    ).first()
    if learned is not None:
        ids.add(int(learned.catalog_issue_id))
    return ids


def barcode_catalog_identity_conflict(session: Session, barcode: str) -> bool:
    return len(distinct_catalog_issue_ids_for_barcode(session, barcode)) > 1


def cover_contradicts_local_barcode(
    session: Session,
    *,
    image_path: Path,
    catalog_issue_id: int,
) -> tuple[bool, str]:
    """True only when cover fingerprint strongly indicates a different issue than the barcode match."""
    score = fingerprint_match_score_for_crop_path(
        session, crop_path=image_path, catalog_issue_id=catalog_issue_id
    )
    if score >= 70.0:
        return False, ""
    hits = search_catalog_fingerprint_hits_for_crop_path(session, crop_path=image_path, limit=1)
    if not hits:
        return False, ""
    top = hits[0]
    if int(top.issue_id) == int(catalog_issue_id):
        return False, ""
    if top.confidence >= _COVER_CONTRADICT_THRESHOLD:
        return (
            True,
            f"Cover fingerprint strongly suggests a different issue ({top.confidence:.0%}) "
            f"than barcode match #{catalog_issue_id}.",
        )
    return False, ""


def ocr_barcode_info_note(
    *,
    normalized_barcode: str,
    ocr_supplement: str,
    matched_series: str | None,
    matched_issue_number: str | None,
) -> str | None:
    """Non-blocking note when printed OCR issue differs from barcode-resolved catalog issue."""
    encoded = barcode_encoded_issue_number(normalized_barcode)
    if encoded is None:
        return None
    ocr_digits = "".join(ch for ch in (ocr_supplement or "") if ch.isdigit())
    if len(ocr_digits) != 5:
        return None
    ocr_issue = int(ocr_digits[:3])
    if ocr_issue == encoded:
        return None
    series = (matched_series or "this series").strip()
    issue = (matched_issue_number or str(encoded)).strip().lstrip("#")
    return (
        f"Printed supplement OCR read issue #{ocr_issue}, but barcode matched {series} #{issue}."
    )


def ocr_issue_from_supplement(supplement: str) -> int | None:
    parsed = parse_comic_upc_extension(supplement)
    return parsed.issue_number if parsed is not None else None
