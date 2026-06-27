"""Intake scanner confidence: when full UPC+5 + local catalog wins over OCR noise."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
    validate_barcode_catalog_match,
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

logger = logging.getLogger(__name__)

LOCAL_TRUSTED_MATCH_SOURCES = frozenset({MATCH_SOURCE_LEARNED, MATCH_SOURCE_CATALOG_UPC})

# Block auto-match only on near-certain fingerprint disagreement when barcode is weak.
FINGERPRINT_BLOCK_THRESHOLD = 0.995
# Informational note when fingerprint favors another issue but barcode is verified.
FINGERPRINT_INFO_THRESHOLD = 0.75

COVER_AGREE_SCORE = 70.0


@dataclass(frozen=True)
class CoverFingerprintOutcome:
    blocks_auto_match: bool
    info_message: str | None
    fingerprint_issue_id: int | None
    fingerprint_confidence: float | None
    disagrees: bool


def has_full_direct_market_barcode(normalized: str) -> bool:
    digits = normalize_upc(normalized)
    return len(digits) >= 17 and not direct_market_requires_supplement_key(digits)


def is_local_trusted_match_source(source: str | None) -> bool:
    return (source or "") in LOCAL_TRUSTED_MATCH_SOURCES


def is_validated_full_upc_exact_match(
    normalized_barcode: str,
    *,
    publisher: str | None,
    issue_number: str | None,
    year: str | None,
) -> bool:
    """True when full UPC+5 passes safe-match validation against the catalog row."""
    if not has_full_direct_market_barcode(normalized_barcode):
        return False
    validation = validate_barcode_catalog_match(
        normalized_barcode,
        publisher=publisher,
        issue_number=issue_number,
        year=year,
    )
    return validation.status == "exact_match"


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


def log_barcode_fingerprint_disagreement(
    *,
    intake_item_id: int | None,
    barcode_issue_id: int,
    fingerprint_issue_id: int | None,
    fingerprint_confidence: float | None,
    final_issue_id: int,
    outcome: str,
) -> None:
    logger.info(
        "intake.barcode_fingerprint.disagreement item_id=%s barcode_issue_id=%s "
        "fingerprint_issue_id=%s fingerprint_confidence=%s final_issue_id=%s outcome=%s",
        intake_item_id,
        barcode_issue_id,
        fingerprint_issue_id,
        fingerprint_confidence,
        final_issue_id,
        outcome,
    )


def log_barcode_fingerprint_user_resolution(
    *,
    intake_item_id: int,
    barcode_issue_id: int | None,
    fingerprint_issue_id: int | None,
    fingerprint_confidence: float | None,
    chosen_issue_id: int,
    user_action: str,
) -> None:
    logger.info(
        "intake.barcode_fingerprint.user_resolution item_id=%s barcode_issue_id=%s "
        "fingerprint_issue_id=%s fingerprint_confidence=%s chosen_issue_id=%s user_action=%s",
        intake_item_id,
        barcode_issue_id,
        fingerprint_issue_id,
        fingerprint_confidence,
        chosen_issue_id,
        user_action,
    )


def evaluate_cover_fingerprint_vs_barcode(
    session: Session,
    *,
    image_path: Path,
    catalog_issue_id: int,
    barcode_validation_strong: bool,
    intake_item_id: int | None = None,
    final_issue_id: int | None = None,
) -> CoverFingerprintOutcome:
    """
    Compare cover fingerprint to barcode-resolved issue.

    Verified full UPC+5 matches are never blocked solely by fingerprint; disagreement is informational.
    """
    score = fingerprint_match_score_for_crop_path(
        session, crop_path=image_path, catalog_issue_id=catalog_issue_id
    )
    if score >= COVER_AGREE_SCORE:
        return CoverFingerprintOutcome(False, None, None, None, False)

    hits = search_catalog_fingerprint_hits_for_crop_path(session, crop_path=image_path, limit=1)
    if not hits:
        return CoverFingerprintOutcome(False, None, None, None, False)

    top = hits[0]
    fp_issue = int(top.issue_id)
    fp_conf = float(top.confidence)
    if fp_issue == int(catalog_issue_id):
        return CoverFingerprintOutcome(False, None, fp_issue, fp_conf, False)

    disagrees = True
    chosen = int(final_issue_id if final_issue_id is not None else catalog_issue_id)

    if barcode_validation_strong:
        log_barcode_fingerprint_disagreement(
            intake_item_id=intake_item_id,
            barcode_issue_id=catalog_issue_id,
            fingerprint_issue_id=fp_issue,
            fingerprint_confidence=fp_conf,
            final_issue_id=chosen,
            outcome="informational",
        )
        info = None
        if fp_conf >= FINGERPRINT_INFO_THRESHOLD:
            info = (
                f"Cover fingerprint favors another issue ({fp_conf:.0%}). Review if desired."
            )
        return CoverFingerprintOutcome(False, info, fp_issue, fp_conf, True)

    log_barcode_fingerprint_disagreement(
        intake_item_id=intake_item_id,
        barcode_issue_id=catalog_issue_id,
        fingerprint_issue_id=fp_issue,
        fingerprint_confidence=fp_conf,
        final_issue_id=chosen,
        outcome="blocked" if fp_conf >= FINGERPRINT_BLOCK_THRESHOLD else "weak_barcode_review",
    )

    if fp_conf >= FINGERPRINT_BLOCK_THRESHOLD:
        return CoverFingerprintOutcome(
            True,
            (
                f"Cover fingerprint strongly suggests a different issue ({fp_conf:.0%}) "
                f"than barcode match #{catalog_issue_id}."
            ),
            fp_issue,
            fp_conf,
            True,
        )

    return CoverFingerprintOutcome(False, None, fp_issue, fp_conf, True)


def cover_contradicts_local_barcode(
    session: Session,
    *,
    image_path: Path,
    catalog_issue_id: int,
    barcode_validation_strong: bool = True,
    intake_item_id: int | None = None,
) -> tuple[bool, str]:
    """Backward-compatible wrapper; prefer evaluate_cover_fingerprint_vs_barcode."""
    outcome = evaluate_cover_fingerprint_vs_barcode(
        session,
        image_path=image_path,
        catalog_issue_id=catalog_issue_id,
        barcode_validation_strong=barcode_validation_strong,
        intake_item_id=intake_item_id,
        final_issue_id=catalog_issue_id,
    )
    if outcome.blocks_auto_match:
        return True, outcome.info_message or ""
    return False, ""


def fingerprint_note_from_outcome(outcome: CoverFingerprintOutcome) -> str | None:
    if outcome.blocks_auto_match:
        return outcome.info_message
    return outcome.info_message


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


def combine_info_notes(*notes: str | None) -> str | None:
    parts = [n.strip() for n in notes if n and n.strip()]
    if not parts:
        return None
    return " ".join(parts)
