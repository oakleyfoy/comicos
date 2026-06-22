"""Match a GPT vision read to the master catalog (multi-book photo import).

Per-book matching uses **barcode**, then **cover fingerprint** (when a per-book crop
exists), then scored **text** search over ``catalog_issue / catalog_series /
catalog_publisher``. The chosen match + its cover URL are written onto the read; the
remaining candidates are kept as alternates so the reviewer can switch the match manually.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pathlib import Path

from sqlmodel import Session, select

from app.models.catalog_master import CatalogUpc
from app.models.photo_import import PhotoImportDetectedBook, PhotoImportImage
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name, normalize_upc
from app.services.photo_import_crop_service import resolve_crop_abs_path
from app.services.photo_import_fingerprint_service import search_catalog_fingerprint_hits_for_crop_path
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.recognition.catalog_matcher import (
    CATALOG_FINGERPRINT_VERIFIED_THRESHOLD,
    load_catalog_issue_identity,
)
from app.services.recognition.recognition_catalog_candidate_service import search_catalog_candidates

logger = logging.getLogger(__name__)

_MAX_ALTERNATES = 6


def _series_aligns(vision_series: str | None, catalog_series: str | None) -> bool:
    if not (vision_series or "").strip():
        return True
    if not (catalog_series or "").strip():
        return False
    left = normalize_series_name(vision_series)
    right = normalize_series_name(catalog_series)
    if left == right:
        return True
    return left in right or right in left


def _issue_aligns(vision_issue: str | None, catalog_issue: str | None) -> bool:
    if not (vision_issue or "").strip():
        return True
    if not (catalog_issue or "").strip():
        return False
    return normalize_issue_number(vision_issue) == normalize_issue_number(catalog_issue)


def _vision_has_identity(read: PhotoImportVisionRead) -> bool:
    return bool((read.series or "").strip() and (read.issue_number or "").strip())


def _match_aligns_with_vision(read: PhotoImportVisionRead, match: CatalogMatchResult) -> bool:
    if match.catalog_issue_id is None:
        return False
    if not _vision_has_identity(read):
        return True
    return _series_aligns(read.series, match.series) and _issue_aligns(read.issue_number, match.issue_number)


def _alternate_from_result(match: CatalogMatchResult) -> CatalogMatchAlternate:
    return CatalogMatchAlternate(
        catalog_issue_id=int(match.catalog_issue_id or 0),
        series=match.series,
        issue_number=match.issue_number,
        publisher=match.publisher,
        cover_url=match.cover_url,
        confidence=float(match.confidence or 0.0),
    )


def _prepend_alternates(primary: CatalogMatchResult, *extra: CatalogMatchAlternate) -> None:
    seen = {primary.catalog_issue_id}
    merged = list(primary.alternates)
    for alt in extra:
        if alt.catalog_issue_id in seen:
            continue
        merged.insert(0, alt)
        seen.add(alt.catalog_issue_id)
    primary.alternates = merged[:_MAX_ALTERNATES]


def _merge_text_alternates(primary: CatalogMatchResult, text: CatalogMatchResult) -> CatalogMatchResult:
    primary.alternates = [a for a in primary.alternates if a.catalog_issue_id != primary.catalog_issue_id]
    if text.catalog_issue_id and text.catalog_issue_id != primary.catalog_issue_id:
        _prepend_alternates(
            primary,
            CatalogMatchAlternate(
                catalog_issue_id=text.catalog_issue_id,
                series=text.series,
                issue_number=text.issue_number,
                publisher=text.publisher,
                cover_url=text.cover_url,
                confidence=float(text.confidence or 0.0),
            ),
        )
    for alt in text.alternates:
        if alt.catalog_issue_id != primary.catalog_issue_id and all(
            a.catalog_issue_id != alt.catalog_issue_id for a in primary.alternates
        ):
            primary.alternates.append(alt)
    primary.alternates = primary.alternates[:_MAX_ALTERNATES]
    return primary


@dataclass
class CatalogMatchAlternate:
    catalog_issue_id: int
    series: str | None
    issue_number: str | None
    publisher: str | None
    cover_url: str | None
    confidence: float

    def as_dict(self) -> dict:
        return {
            "catalog_issue_id": self.catalog_issue_id,
            "series": self.series,
            "issue_number": self.issue_number,
            "publisher": self.publisher,
            "cover_url": self.cover_url,
            "confidence": self.confidence,
        }


@dataclass
class CatalogMatchResult:
    catalog_issue_id: int | None = None
    catalog_variant_id: int | None = None
    cover_url: str | None = None
    method: str = "none"  # "upc" | "fingerprint" | "text" | "manual" | "none"
    confidence: float | None = None
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    alternates: list[CatalogMatchAlternate] = field(default_factory=list)


def _upc_match(session: Session, barcode: str | None) -> CatalogMatchResult | None:
    if not barcode or not barcode.strip():
        return None
    normalized = normalize_upc(barcode)
    if not normalized:
        return None
    row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)).first()
    if row is None or row.issue_id is None:
        return None
    identity = load_catalog_issue_identity(session, int(row.issue_id))
    return CatalogMatchResult(
        catalog_issue_id=int(row.issue_id),
        catalog_variant_id=int(row.variant_id) if row.variant_id is not None else None,
        cover_url=identity.cover_image_url if identity else None,
        method="upc",
        confidence=1.0,
        series=identity.series if identity else None,
        issue_number=identity.issue_number if identity else None,
        publisher=identity.publisher if identity else None,
    )


def _text_match(
    session: Session,
    *,
    series: str | None,
    issue_number: str | None,
    publisher: str | None,
) -> CatalogMatchResult:
    if not (series or "").strip():
        return CatalogMatchResult()
    candidates = search_catalog_candidates(
        session,
        series=series,
        issue_number=issue_number,
        publisher=publisher,
        limit=_MAX_ALTERNATES,
        publisher_strict=False,
    )
    if not candidates:
        return CatalogMatchResult()
    alternates = [
        CatalogMatchAlternate(
            catalog_issue_id=int(c.catalog_issue_id),
            series=c.series,
            issue_number=c.issue_number,
            publisher=c.publisher,
            cover_url=c.cover_image_url,
            confidence=float(c.confidence),
        )
        for c in candidates
    ]
    top = alternates[0]
    return CatalogMatchResult(
        catalog_issue_id=top.catalog_issue_id,
        catalog_variant_id=None,
        cover_url=top.cover_url,
        method="text",
        confidence=top.confidence,
        series=top.series,
        issue_number=top.issue_number,
        publisher=top.publisher,
        alternates=alternates[1:],
    )


def resolve_crop_path_for_vision_read(session: Session, read: PhotoImportVisionRead) -> Path | None:
    """Per-book crop from detection order, else the full photo for single-book uploads."""
    detections = list(
        session.exec(
            select(PhotoImportDetectedBook)
            .where(PhotoImportDetectedBook.image_id == read.image_id)
            .order_by(PhotoImportDetectedBook.id.asc())
        ).all()
    )
    idx = int(read.detection_index or 0)
    if idx < len(detections):
        crop = resolve_crop_abs_path(detections[idx].crop_path)
        if crop is not None:
            return crop
    image = session.get(PhotoImportImage, read.image_id)
    if image is None:
        return None
    return resolve_photo_import_storage_path(image.storage_path, image_id=int(read.image_id))


def _fingerprint_match(session: Session, crop_path: Path) -> CatalogMatchResult | None:
    hits = search_catalog_fingerprint_hits_for_crop_path(session, crop_path=crop_path, limit=_MAX_ALTERNATES + 1)
    if not hits:
        return None
    top = hits[0]
    if top.confidence < CATALOG_FINGERPRINT_VERIFIED_THRESHOLD:
        return None
    identity = load_catalog_issue_identity(session, top.issue_id)
    if identity is None:
        return None
    alternates: list[CatalogMatchAlternate] = []
    for hit in hits[1:]:
        alt_identity = load_catalog_issue_identity(session, hit.issue_id)
        if alt_identity is None:
            continue
        alternates.append(
            CatalogMatchAlternate(
                catalog_issue_id=hit.issue_id,
                series=alt_identity.series,
                issue_number=alt_identity.issue_number,
                publisher=alt_identity.publisher,
                cover_url=alt_identity.cover_image_url,
                confidence=hit.confidence,
            )
        )
    return CatalogMatchResult(
        catalog_issue_id=top.issue_id,
        catalog_variant_id=None,
        cover_url=identity.cover_image_url,
        method="fingerprint",
        confidence=top.confidence,
        series=identity.series,
        issue_number=identity.issue_number,
        publisher=identity.publisher,
        alternates=alternates[:_MAX_ALTERNATES],
    )


def match_read_to_catalog(session: Session, read: PhotoImportVisionRead) -> CatalogMatchResult:
    """Resolve catalog match: trust barcode/fingerprint only when they agree with GPT series/issue."""
    text = _text_match(
        session, series=read.series, issue_number=read.issue_number, publisher=read.publisher
    )
    demoted: list[CatalogMatchAlternate] = []

    upc = _upc_match(session, read.barcode)
    if upc is not None and upc.catalog_issue_id is not None:
        if _match_aligns_with_vision(read, upc):
            return _merge_text_alternates(upc, text)
        logger.info(
            "photo_import.catalog_match upc_rejected read_id=%s catalog_issue_id=%s vision=%s #%s",
            read.id,
            upc.catalog_issue_id,
            read.series,
            read.issue_number,
        )
        demoted.append(_alternate_from_result(upc))

    crop = resolve_crop_path_for_vision_read(session, read)
    if crop is not None:
        fp = _fingerprint_match(session, crop)
        if fp is not None and fp.catalog_issue_id is not None:
            if _match_aligns_with_vision(read, fp):
                result = _merge_text_alternates(fp, text)
                _prepend_alternates(result, *demoted)
                return result
            logger.info(
                "photo_import.catalog_match fingerprint_rejected read_id=%s catalog_issue_id=%s vision=%s #%s",
                read.id,
                fp.catalog_issue_id,
                read.series,
                read.issue_number,
            )
            demoted.append(_alternate_from_result(fp))

    if text.catalog_issue_id is not None:
        for alt in demoted:
            if alt.catalog_issue_id != text.catalog_issue_id:
                _prepend_alternates(text, alt)
        return text

    # GPT identified the book but nothing in the catalog aligns. Do not surface a
    # conflicting barcode/fingerprint cover; keep those as alternates only.
    if demoted and _vision_has_identity(read):
        return CatalogMatchResult(method="none", alternates=demoted[:_MAX_ALTERNATES])

    if demoted:
        first = demoted[0]
        return CatalogMatchResult(
            catalog_issue_id=first.catalog_issue_id,
            catalog_variant_id=None,
            cover_url=first.cover_url,
            method="upc" if upc and upc.catalog_issue_id == first.catalog_issue_id else "fingerprint",
            confidence=first.confidence,
            series=first.series,
            issue_number=first.issue_number,
            publisher=first.publisher,
            alternates=demoted[1:_MAX_ALTERNATES],
        )
    return CatalogMatchResult()


def apply_match_to_read(read: PhotoImportVisionRead, match: CatalogMatchResult) -> None:
    """Write a match result onto a read row (does not commit)."""
    read.catalog_issue_id = match.catalog_issue_id
    read.catalog_variant_id = match.catalog_variant_id
    read.catalog_cover_url = match.cover_url
    read.match_method = match.method
    read.match_confidence = match.confidence
    raw = dict(read.raw_response or {})
    raw["catalog_alternates"] = [a.as_dict() for a in match.alternates]
    raw["catalog_identity"] = {
        "series": match.series,
        "issue_number": match.issue_number,
        "publisher": match.publisher,
    }
    read.raw_response = raw


def match_and_apply(session: Session, read: PhotoImportVisionRead) -> CatalogMatchResult:
    match = match_read_to_catalog(session, read)
    apply_match_to_read(read, match)
    logger.info(
        "photo_import.catalog_match read_id=%s method=%s catalog_issue_id=%s confidence=%s",
        read.id,
        match.method,
        match.catalog_issue_id,
        match.confidence,
    )
    return match


def rematch_stale_automatic_catalog_link(session: Session, read: PhotoImportVisionRead) -> bool:
    """Re-run matching when a barcode/fingerprint hit disagrees with GPT fields (e.g. after logic fixes)."""
    if read.match_method not in ("upc", "fingerprint") or read.catalog_issue_id is None:
        return False
    if not _vision_has_identity(read):
        return False
    identity = (read.raw_response or {}).get("catalog_identity") or {}
    current = CatalogMatchResult(
        catalog_issue_id=read.catalog_issue_id,
        catalog_variant_id=read.catalog_variant_id,
        cover_url=read.catalog_cover_url,
        method=read.match_method or "none",
        confidence=read.match_confidence,
        series=identity.get("series") or read.series,
        issue_number=identity.get("issue_number") or read.issue_number,
        publisher=identity.get("publisher") or read.publisher,
    )
    if _match_aligns_with_vision(read, current):
        return False
    match = match_read_to_catalog(session, read)
    apply_match_to_read(read, match)
    session.add(read)
    session.commit()
    session.refresh(read)
    logger.info(
        "photo_import.catalog_match rematch_stale read_id=%s old_issue=%s new_issue=%s method=%s",
        read.id,
        current.catalog_issue_id,
        match.catalog_issue_id,
        match.method,
    )
    return True


def choose_match_for_read(
    session: Session, read: PhotoImportVisionRead, *, catalog_issue_id: int
) -> CatalogMatchResult:
    """Manually pin the read to a specific catalog issue (from an alternate)."""
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Catalog issue not found"
        )
    # Keep the previously surfaced alternates available for further switching.
    existing_alternates: list[CatalogMatchAlternate] = []
    for entry in (read.raw_response or {}).get("catalog_alternates", []) or []:
        try:
            existing_alternates.append(CatalogMatchAlternate(**entry))
        except TypeError:
            continue
    result = CatalogMatchResult(
        catalog_issue_id=catalog_issue_id,
        catalog_variant_id=None,
        cover_url=identity.cover_image_url,
        method="manual",
        confidence=1.0,
        series=identity.series,
        issue_number=identity.issue_number,
        publisher=identity.publisher,
        alternates=[a for a in existing_alternates if a.catalog_issue_id != catalog_issue_id],
    )
    apply_match_to_read(read, result)
    return result
