"""Barcode-first book identification (no GPT cover read)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.models.photo_import import (
    IMAGE_STATUS_FAILED,
    IMAGE_STATUS_PROCESSED,
    IMAGE_ROLE_BARCODE_PRIMARY,
    PhotoImportImage,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.barcode_validation_service import (
    MatchStatus,
    base_upc,
    parse_comic_upc_extension,
    supplement_extension,
    validate_barcode_catalog_match,
)
from app.services.catalog_ingestion_service import (
    comic_barcode_lookup_keys_for_search,
    direct_market_requires_supplement_key,
    normalize_upc,
)
from app.services.photo_import_barcode_vision import normalize_comic_scan_barcode
from app.services.p100_barcode_extraction_service import extract_barcode_from_image
from app.services.p100_comicvine_barcode_lookup_service import lookup_comicvine_by_barcode
from app.services.photo_import_vision_sandbox_service import (
    VisionSandboxReadResult,
    persist_vision_read,
    vision_reads_for_image,
)
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)

SUGGESTED_ACTION_COVER = "Use cover scan or find in catalog"


class BarcodeIdentifyError(Exception):
    """Barcode scan could not produce a book identification."""


@dataclass
class BarcodeIdentifyOutcome:
    """Structured result of a barcode-primary identification attempt."""

    status: MatchStatus
    detected_barcode: str = ""
    base_upc: str = ""
    reason: str = ""
    suggested_action: str = ""
    rows: list[PhotoImportVisionRead] = field(default_factory=list)


def is_barcode_primary_image(image: PhotoImportImage) -> bool:
    return str(getattr(image, "image_role", "") or "").strip().lower() == IMAGE_ROLE_BARCODE_PRIMARY


def _year_from_cover_date(cover_date: str | None) -> str:
    if not (cover_date or "").strip():
        return ""
    match = re.search(r"(19|20)\d{2}", cover_date)
    return match.group(0) if match else ""


def _local_catalog_hit(session: Session, barcode: str) -> dict[str, Any] | None:
    for key in comic_barcode_lookup_keys_for_search(barcode):
        if len(key) < 17 and direct_market_requires_supplement_key(barcode):
            continue
        row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == key)).first()
        if row is None or row.issue_id is None:
            continue
        identity = load_catalog_issue_identity(session, int(row.issue_id))
        if identity is None:
            continue
        issue = session.get(CatalogIssue, int(row.issue_id))
        year = ""
        if issue is not None and issue.cover_date is not None:
            year = str(issue.cover_date.year)
        return {
            "source": "catalog_upc",
            "catalog_issue_id": int(row.issue_id),
            "catalog_variant_id": int(row.variant_id) if row.variant_id is not None else None,
            "barcode_key": key,
            "series": identity.series,
            "issue_number": identity.issue_number,
            "publisher": identity.publisher,
            "year": year,
            "cover_image_url": identity.cover_image_url,
        }
    return None


def _vision_result_from_hit(
    *,
    barcode: str,
    extraction: dict[str, Any],
    local: dict[str, Any] | None,
    comicvine: dict[str, Any] | None,
) -> VisionSandboxReadResult:
    if local:
        return VisionSandboxReadResult(
            publisher=(local.get("publisher") or "")[:256],
            series=(local.get("series") or "")[:512],
            issue_number=(local.get("issue_number") or "")[:64] if local.get("issue_number") else None,
            issue_title="",
            variant_description="",
            year="",
            cover_date="",
            barcode=barcode[:64],
            confidence=0.99,
            reasoning="Identified from UPC (local catalog barcode lookup).",
            possible_alternates=[],
            raw_response={
                "identification_mode": "barcode_primary",
                "barcode_extraction": extraction,
                "local_catalog": local,
            },
            raw_response_text="",
        )

    cv = comicvine or {}
    cover_date = str(cv.get("cover_date") or "").strip()
    return VisionSandboxReadResult(
        publisher=(cv.get("publisher") or "")[:256],
        series=(cv.get("series") or "")[:512],
        issue_number=(cv.get("issue_number") or "")[:64] if cv.get("issue_number") else None,
        issue_title=(cv.get("name") or "")[:512],
        variant_description="",
        year=_year_from_cover_date(cover_date),
        cover_date=cover_date[:32],
        barcode=barcode[:64],
        confidence=0.97,
        reasoning="Identified from UPC (ComicVine barcode lookup). Use Validate on demand to import into local catalog.",
        possible_alternates=[],
        raw_response={
            "identification_mode": "barcode_primary",
            "barcode_extraction": extraction,
            "comicvine_barcode_match": cv,
        },
        raw_response_text="",
    )


def _mark_image(session: Session, image: PhotoImportImage, status: str) -> None:
    image.status = status
    session.add(image)
    session.commit()


def identify_and_persist_barcode_primary(
    session: Session,
    *,
    image: PhotoImportImage,
    image_bytes: bytes,
) -> BarcodeIdentifyOutcome:
    """Decode UPC from a barcode photo and identify the book without a GPT cover read.

    Returns a structured outcome. ``exact_match`` carries persisted reads; every other
    status (``no_safe_match``, ``ambiguous_base_upc``, ``not_found``, ``unreadable``)
    carries the detected barcode and a reason so the client can refuse a bad match.
    """
    image_id = int(image.id or 0)
    logger.info("photo_import.barcode_primary.started image_id=%s", image_id)

    extraction = extract_barcode_from_image(
        image_bytes,
        allow_gpt_fallback=True,
        log_context=f"photo_import barcode_primary image_id={image_id}",
    )
    barcode = extraction.get("barcode")
    raw_detected = str(barcode or "")
    if not barcode:
        logger.info("photo_import.barcode_primary.unreadable image_id=%s", image_id)
        _mark_image(session, image, IMAGE_STATUS_FAILED)
        return BarcodeIdentifyOutcome(
            status="unreadable",
            reason=(
                "Could not read a UPC from this photo. Fill the frame with the barcode, "
                "or switch to cover photo for older books."
            ),
            suggested_action=SUGGESTED_ACTION_COVER,
        )

    normalized = normalize_comic_scan_barcode(raw_detected) or normalize_upc(raw_detected)
    ext = supplement_extension(normalized)
    logger.info(
        "photo_import.barcode_primary.detected image_id=%s raw=%s normalized=%s base=%s extension=%s",
        image_id,
        raw_detected,
        normalized,
        base_upc(normalized),
        ext or "(none)",
    )

    # Modern direct-market UPC without its 5-digit supplement is ambiguous: never auto-match.
    if direct_market_requires_supplement_key(normalized):
        base = base_upc(normalized)
        logger.info(
            "photo_import.barcode_primary.ambiguous_base_upc image_id=%s base=%s", image_id, base
        )
        _mark_image(session, image, IMAGE_STATUS_PROCESSED)
        return BarcodeIdentifyOutcome(
            status="ambiguous_base_upc",
            detected_barcode=base,
            base_upc=base,
            reason=(
                f"Read the main UPC ({base}) but not the 5-digit supplement. DC/Marvel boxes use a "
                "second small barcode—include both in one photo, or use cover scan."
            ),
            suggested_action=SUGGESTED_ACTION_COVER,
        )

    local = _local_catalog_hit(session, normalized)
    comicvine = None if local else lookup_comicvine_by_barcode(normalized)
    matched = local or (comicvine if comicvine and comicvine.get("matched") else None)

    if matched is None:
        logger.info("photo_import.barcode_primary.not_found image_id=%s barcode=%s", image_id, normalized)
        _mark_image(session, image, IMAGE_STATUS_PROCESSED)
        return BarcodeIdentifyOutcome(
            status="not_found",
            detected_barcode=normalized,
            base_upc=base_upc(normalized),
            reason=f"UPC {normalized} is not in our catalog or ComicVine yet.",
            suggested_action=SUGGESTED_ACTION_COVER,
        )

    # Log the selected candidate before validating it.
    cover_date = str(matched.get("cover_date") or "")
    matched_year = matched.get("year") or _year_from_cover_date(cover_date)
    logger.info(
        "photo_import.barcode_primary.candidate image_id=%s source=%s issue_id=%s "
        "publisher=%r series=%r issue=%r year=%r",
        image_id,
        "catalog_upc" if local else "comicvine",
        matched.get("catalog_issue_id"),
        matched.get("publisher"),
        matched.get("series"),
        matched.get("issue_number"),
        matched_year,
    )

    # Safe-match validation: refuse implausible records (wrong publisher / issue / era).
    validation = validate_barcode_catalog_match(
        normalized,
        publisher=matched.get("publisher"),
        issue_number=matched.get("issue_number"),
        year=matched_year,
    )
    if validation.status != "exact_match":
        logger.warning(
            "photo_import.barcode_primary.rejected image_id=%s barcode=%s reason=%s",
            image_id,
            normalized,
            validation.reason,
        )
        _mark_image(session, image, IMAGE_STATUS_PROCESSED)
        return BarcodeIdentifyOutcome(
            status="no_safe_match",
            detected_barcode=normalized,
            base_upc=base_upc(normalized),
            reason=f"Barcode matched catalog record failed validation: {validation.reason}",
            suggested_action=SUGGESTED_ACTION_COVER,
        )

    result = _vision_result_from_hit(
        barcode=normalized,
        extraction=extraction,
        local=local,
        comicvine=comicvine if comicvine and comicvine.get("matched") else None,
    )

    existing = vision_reads_for_image(session, image_id=image_id)
    for old in existing:
        session.delete(old)
    if existing:
        session.commit()

    row = persist_vision_read(
        session,
        session_id=int(image.session_id),
        image_id=image_id,
        result=result,
        detection_index=0,
        run_match=True,
    )

    if comicvine and comicvine.get("matched") and row.catalog_issue_id is None and comicvine.get("image_url"):
        row.catalog_cover_url = str(comicvine.get("image_url"))
        session.add(row)
        session.commit()
        session.refresh(row)

    _mark_image(session, image, IMAGE_STATUS_PROCESSED)

    logger.info(
        "photo_import.barcode_primary.success image_id=%s barcode=%s source=%s read_id=%s",
        image_id,
        normalized,
        "catalog_upc" if local else "comicvine",
        row.id,
    )
    return BarcodeIdentifyOutcome(
        status="exact_match",
        detected_barcode=normalized,
        base_upc=base_upc(normalized),
        rows=[row],
    )
