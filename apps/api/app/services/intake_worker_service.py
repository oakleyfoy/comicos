"""Background identification worker for the async intake queue.

Each queued ``IntakeSessionItem`` is processed independently and asynchronously so the
phone scanner never blocks. Identification order favors instant/high-confidence sources:

    1. Learned barcode map (``comic_issue_barcodes``) — instant from prior accepts.
    2. Local catalog UPC table (``catalog_upc``).
    3. ComicVine on-demand lookup (needs review before inventory).

Local catalog misses trigger P106 GCD barcode lookup before ComicVine. Unique exact GCD
matches may auto-import/attach so the scanner never shows a blank identity.

Every candidate is run through safe-match validation so we never auto-match the wrong book.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.models.intake_queue import (
    ComicIssueBarcode,
    ITEM_AUTO_MATCHED,
    ITEM_FAILED,
    ITEM_NEEDS_REVIEW,
    ITEM_PROCESSING,
    ITEM_READY_FOR_REVIEW,
    IntakeItemCandidate,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
    MATCH_SOURCE_COMICVINE,
    MATCH_SOURCE_LEARNED,
    utc_now,
)
from app.services.barcode_validation_service import (
    barcode_encoded_issue_number,
    base_upc,
    effective_publisher_for_barcode,
    supplement_extension,
    validate_barcode_catalog_match,
)
from app.services.barcode_scan_consensus_service import (
    normalize_scan_preserving_supplement,
    validate_single_barcode_read,
)
from app.services.catalog_ingestion_service import (
    comic_barcode_lookup_keys_for_search,
    direct_market_requires_supplement_key,
    normalize_upc,
)
from app.services.intake_barcode_confidence import (
    barcode_catalog_identity_conflict,
    combine_info_notes,
    evaluate_cover_fingerprint_vs_barcode,
    fingerprint_note_from_outcome,
    has_full_direct_market_barcode,
    is_local_trusted_match_source,
    is_validated_full_upc_exact_match,
    log_barcode_fingerprint_user_resolution,
    ocr_barcode_info_note,
)
from app.services.p100_barcode_extraction_service import extract_barcode_from_image
from app.services.p105_comic_barcode_read_service import (
    publisher_validation_for_match,
    read_comic_barcode_from_image_bytes,
)
from app.services.p100_comicvine_barcode_lookup_service import lookup_comicvine_by_barcode
from app.services.photo_import_fingerprint_service import (
    fingerprint_match_score_for_crop_path,
    search_catalog_fingerprint_hits_for_crop_path,
)
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)

# Unique exact GCD barcode hits auto-resolve during scan (no manual CLI).
AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP = True

COVER_FINGERPRINT_AGREE_SCORE = 70.0
# Recognition images below this long edge are too small for barcode OCR/fingerprint.
MIN_RECOGNITION_LONG_EDGE_PX = 600
# Below this byte size an "image" is almost certainly a preview/thumbnail, not a scan.
SUSPICIOUS_MIN_IMAGE_BYTES = 8 * 1024


def image_dimensions_from_bytes(raw: bytes) -> tuple[int, int] | None:
    """Decode width/height without loading pixels into the recognition path; None on failure."""
    import io as _io

    try:
        from PIL import Image as _Image

        with _Image.open(_io.BytesIO(raw)) as im:
            return int(im.width), int(im.height)
    except Exception:  # noqa: BLE001
        return None


def recognition_image_too_small(raw: bytes) -> tuple[bool, int, int, str]:
    """Return (too_small, width, height, reason) for a candidate recognition image."""
    dims = image_dimensions_from_bytes(raw)
    byte_len = len(raw)
    if dims is None:
        return True, 0, 0, f"Captured image could not be decoded ({byte_len} bytes)."
    w_img, h_img = dims
    if max(w_img, h_img) < MIN_RECOGNITION_LONG_EDGE_PX:
        return (
            True,
            w_img,
            h_img,
            (
                f"Input image too small for reliable barcode OCR ({w_img}x{h_img}, {byte_len} bytes; "
                f"need long edge >= {MIN_RECOGNITION_LONG_EDGE_PX}px). Re-scan closer / higher resolution."
            ),
        )
    return False, w_img, h_img, ""


def _year_from_cover_date(cover_date: str | None) -> str:
    match = re.search(r"(18|19|20)\d{2}", str(cover_date or ""))
    return match.group(0) if match else ""


def _clear_candidates(session: Session, item_id: int) -> None:
    rows = session.exec(
        select(IntakeItemCandidate).where(IntakeItemCandidate.item_id == item_id)
    ).all()
    for row in rows:
        session.delete(row)


def _add_candidate(session: Session, *, item_id: int, source: str, rank: int, data: dict[str, Any]) -> None:
    session.add(
        IntakeItemCandidate(
            item_id=item_id,
            catalog_issue_id=data.get("catalog_issue_id"),
            variant_id=data.get("variant_id"),
            publisher=(data.get("publisher") or None),
            series=(data.get("series") or None),
            issue_number=(data.get("issue_number") or None),
            cover_url=(data.get("cover_url") or None),
            score=float(data.get("score") or 0.0),
            source=source,
            rank=rank,
        )
    )


def _catalog_issue_year(session: Session, catalog_issue_id: int) -> str:
    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is not None and issue.cover_date is not None:
        return str(issue.cover_date.year)
    return ""


def _local_candidate(session: Session, *, source: str, catalog_issue_id: int, variant_id: int | None) -> dict[str, Any] | None:
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        return None
    return {
        "source": source,
        "catalog_issue_id": catalog_issue_id,
        "variant_id": variant_id,
        "publisher": identity.publisher,
        "series": identity.series,
        "issue_number": identity.issue_number,
        "cover_url": identity.cover_image_url,
        "year": _catalog_issue_year(session, catalog_issue_id),
    }


def _stamp_item_barcode_identity(item: IntakeSessionItem, normalized: str) -> None:
    """Fill publisher/issue from the barcode when catalog match is not yet linked."""
    pub = effective_publisher_for_barcode(normalized, item.matched_publisher)
    if pub and not (item.matched_publisher or "").strip():
        item.matched_publisher = pub
    encoded = barcode_encoded_issue_number(normalized)
    if encoded is not None and not (item.matched_issue_number or "").strip():
        item.matched_issue_number = str(encoded)


def _candidate_if_valid(barcode: str, cand: dict[str, Any] | None) -> dict[str, Any] | None:
    if cand is None:
        return None
    work = dict(cand)
    if not (work.get("publisher") or "").strip():
        inferred = effective_publisher_for_barcode(barcode, None)
        if inferred:
            work["publisher"] = inferred
    validation = validate_barcode_catalog_match(
        barcode,
        publisher=work.get("publisher"),
        issue_number=work.get("issue_number"),
        year=work.get("year"),
    )
    if validation.status != "exact_match":
        return None
    return work


def _resolve_local_catalog_candidate(session: Session, *, barcode: str) -> dict[str, Any] | None:
    """Learned barcode map and catalog_upc only (no ComicVine, no GCD)."""
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == barcode)
    ).first()
    if learned is not None:
        cand = _local_candidate(
            session,
            source=MATCH_SOURCE_LEARNED,
            catalog_issue_id=int(learned.catalog_issue_id),
            variant_id=learned.variant_id,
        )
        valid = _candidate_if_valid(barcode, cand)
        if valid is not None:
            valid["confidence"] = 0.99
            valid["learned_row"] = learned
            return valid

    for key in comic_barcode_lookup_keys_for_search(barcode):
        if len(key) < 17 and direct_market_requires_supplement_key(barcode):
            continue
        row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == key)).first()
        if row is None or row.issue_id is None:
            continue
        cand = _local_candidate(
            session,
            source=MATCH_SOURCE_CATALOG_UPC,
            catalog_issue_id=int(row.issue_id),
            variant_id=int(row.variant_id) if row.variant_id is not None else None,
        )
        valid = _candidate_if_valid(barcode, cand)
        if valid is not None:
            valid["confidence"] = 0.97
            return valid
    return None


def _resolve_comicvine_candidate(session: Session, *, barcode: str) -> dict[str, Any] | None:
    cv = lookup_comicvine_by_barcode(barcode)
    if cv and cv.get("matched"):
        cover_date = str(cv.get("cover_date") or "")
        cand = {
            "source": MATCH_SOURCE_COMICVINE,
            "catalog_issue_id": None,
            "variant_id": None,
            "publisher": cv.get("publisher"),
            "series": cv.get("series"),
            "issue_number": cv.get("issue_number"),
            "cover_url": cv.get("image_url") or cv.get("cover_url"),
            "year": _year_from_cover_date(cover_date),
            "confidence": 0.8,
        }
        valid = _candidate_if_valid(barcode, cand)
        if valid is not None:
            return valid
    return None


def _resolve_candidate(session: Session, *, barcode: str) -> dict[str, Any] | None:
    """Local catalog first, then ComicVine (used when P106 does not resolve)."""
    local = _resolve_local_catalog_candidate(session, barcode=barcode)
    if local is not None:
        return local
    return _resolve_comicvine_candidate(session, barcode=barcode)


def _scanner_gap_finish_reason(diagnosis: dict[str, Any]) -> str:
    if diagnosis.get("ready_to_auto_import"):
        return "Not in your catalog yet — GCD match found (Import & Accept to add)."
    if diagnosis.get("status") in {"review_required", "conflict"}:
        return "GCD barcode match needs review — pick the issue or use Import & Accept."
    if int(diagnosis.get("gcd_match_count") or 0) == 0:
        return "Not in your catalog yet — use Import & Accept (ComicVine) or pick the issue."
    return "Not in your catalog yet — use Import & Accept or pick the issue."


def _log_scanner_barcode_gap(
    *,
    item_id: int,
    scanner_barcode: str,
    local_catalog_hit: bool,
    p106_called: bool,
    diagnosis: dict[str, Any] | None,
    final_scanner_status: str,
) -> None:
    diag = diagnosis or {}
    logger.info(
        "intake.scanner.barcode_gap item_id=%s scanner_barcode=%s local_catalog_hit=%s "
        "p106_called=%s p106_status=%s p106_gcd_issue_id=%s p106_catalog_issue_id=%s final_scanner_status=%s",
        item_id,
        scanner_barcode,
        local_catalog_hit,
        p106_called,
        diag.get("status"),
        diag.get("gcd_issue_id"),
        diag.get("catalog_issue_id"),
        final_scanner_status,
    )


def _cover_confirms_barcode_match(
    session: Session,
    *,
    image_path: Path,
    catalog_issue_id: int,
    barcode_validation_strong: bool,
    intake_item_id: int | None = None,
) -> tuple[bool, str]:
    outcome = evaluate_cover_fingerprint_vs_barcode(
        session,
        image_path=image_path,
        catalog_issue_id=catalog_issue_id,
        barcode_validation_strong=barcode_validation_strong,
        intake_item_id=intake_item_id,
        final_issue_id=catalog_issue_id,
    )
    if outcome.blocks_auto_match:
        return False, outcome.info_message or "Cover fingerprint overrides weak barcode match."
    score = fingerprint_match_score_for_crop_path(
        session, crop_path=image_path, catalog_issue_id=catalog_issue_id
    )
    if score >= COVER_FINGERPRINT_AGREE_SCORE:
        return True, f"Cover fingerprint agrees ({score:.0f}%)."
    if outcome.disagrees and outcome.fingerprint_confidence is not None:
        return (
            False,
            f"Cover fingerprint points to a different issue (top score {outcome.fingerprint_confidence:.0%}) "
            f"than barcode match #{catalog_issue_id} (cover score {score:.0f}%).",
        )
    return False, f"Low cover fingerprint confidence ({score:.0f}%) for barcode match."


def process_intake_item(session: Session, *, item_id: int) -> str:
    """Identify a single queued intake item. Returns the resulting status."""
    item = session.get(IntakeSessionItem, item_id)
    if item is None:
        return "missing"

    item.status = ITEM_PROCESSING
    session.add(item)
    session.commit()

    try:
        abs_path = resolve_photo_import_storage_path(item.storage_path, image_id=item_id)
        if not abs_path.is_file():
            return _fail(session, item, "Captured image is missing from storage.")
        image_bytes = abs_path.read_bytes()

        too_small, img_w, img_h, small_reason = recognition_image_too_small(image_bytes)
        logger.info(
            "intake.item.image item_id=%s bytes=%s width=%s height=%s path=%s too_small=%s",
            item_id,
            len(image_bytes),
            img_w,
            img_h,
            abs_path,
            too_small,
        )
        if too_small:
            # Never run barcode OCR / fingerprint matching on thumbnail-sized input.
            return _finish(session, item, status=ITEM_FAILED, reason=small_reason)

        p105 = read_comic_barcode_from_image_bytes(
            image_bytes,
            session=session,
            cover_path=abs_path,
            intake_item_id=item_id,
            log_context=f"intake item_id={item_id}",
            supplement_frame_bytes=[
                p.read_bytes()
                for p in sorted(abs_path.parent.glob(f"{abs_path.stem}_f*.jpg"))
                if p.is_file()
            ],
        )
        item.barcode_read_json = p105.to_json()

        barcode = p105.reconstructed_full or p105.main_upc or item.raw_barcode
        if not barcode and not p105.main_upc:
            extraction = extract_barcode_from_image(
                image_bytes,
                allow_gpt_fallback=True,
                log_context=f"intake item_id={item_id}",
            )
            barcode = extraction.get("barcode") or item.raw_barcode
        if not barcode:
            return _finish(
                session,
                item,
                status=ITEM_FAILED,
                reason="Could not read a barcode from this photo.",
            )

        raw_digits = str(barcode)
        if p105.reconstructed_full and len(p105.reconstructed_full) >= 17:
            normalized = p105.reconstructed_full[:64]
            scan_validation = validate_single_barcode_read(normalized)
        else:
            scan_validation = validate_single_barcode_read(raw_digits)
        if scan_validation.acceptance == "rejected_checksum":
            corrected = scan_validation.possible_corrected
            hint = f" Suggested correction: {corrected}." if corrected else ""
            return _finish(
                session,
                item,
                status=ITEM_FAILED,
                reason=f"UPC/EAN check digit failed.{hint}",
            )

        normalized = scan_validation.normalized or normalize_scan_preserving_supplement(raw_digits)
        item.raw_barcode = scan_validation.raw_scan[:64] or raw_digits[:64]
        item.normalized_barcode = normalized[:64]
        item.base_upc = (scan_validation.base_upc or base_upc(normalized))[:16]
        item.extension = scan_validation.extension or supplement_extension(normalized) or None
        _stamp_item_barcode_identity(item, normalized)

        local_full_barcode = has_full_direct_market_barcode(normalized)
        if local_full_barcode:
            p105_reason = ""
        elif p105.inferred_supplement:
            p105_reason = p105.review_reason or "Barcode components unstable — review required."
        elif p105.supplement_disagreement and not (
            p105.decoded_supplement
            and p105.final_supplement == p105.decoded_supplement
            and (p105.supplement_decode_confidence or 0) >= 0.85
        ):
            p105_reason = p105.review_reason or "Barcode components unstable — review required."
        else:
            p105_reason = ""
        logger.info(
            "intake.item.detected item_id=%s raw=%s normalized=%s base=%s ext=%s",
            item_id,
            barcode,
            normalized,
            item.base_upc,
            item.extension or "(none)",
        )

        # Modern direct-market UPC without the 5-digit supplement is ambiguous.
        if direct_market_requires_supplement_key(normalized):
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=f"Read base UPC {item.base_upc} but not the 5-digit supplement (ambiguous).",
            )

        candidate = _resolve_local_catalog_candidate(session, barcode=normalized)
        local_catalog_hit = candidate is not None
        gap_diag: dict[str, Any] | None = None
        p106_called = False

        if candidate is None:
            from app.services.p105_barcode_repair_service import record_missing_barcode_queue
            from app.services.gcd_catalog_import_dashboard_service import resolve_cache_path, resolve_gcd_path
            from app.services.p106_barcode_gap_resolver_service import (
                apply_barcode_gap_display_to_intake_item,
                diagnose_barcode_gap,
                merge_barcode_gap_into_barcode_read,
                resolve_barcode_gap,
                should_auto_resolve_barcode_gap_on_scan,
            )

            record_missing_barcode_queue(session, item=item)
            p106_called = True
            try:
                gap_diag = diagnose_barcode_gap(
                    session,
                    barcode=normalized,
                    gcd_path=resolve_gcd_path(None),
                    cache_path=resolve_cache_path(None),
                )
                item.barcode_read_json = merge_barcode_gap_into_barcode_read(
                    item.barcode_read_json,
                    gap_diag,
                )
                apply_barcode_gap_display_to_intake_item(item, gap_diag)
            except Exception:
                logger.warning("p106.barcode_gap.diagnose_failed item_id=%s", item_id, exc_info=True)
                gap_diag = None

            if gap_diag and AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP and should_auto_resolve_barcode_gap_on_scan(gap_diag):
                try:
                    resolve_barcode_gap(
                        session,
                        barcode=normalized,
                        gcd_path=resolve_gcd_path(None),
                        cache_path=resolve_cache_path(None),
                        confirm_write=True,
                        intake_item_id=int(item.id or 0),
                    )
                    candidate = _resolve_local_catalog_candidate(session, barcode=normalized)
                    local_catalog_hit = candidate is not None
                except Exception:
                    logger.warning(
                        "p106.barcode_gap.auto_resolve_failed item_id=%s barcode=%s",
                        item_id,
                        normalized,
                        exc_info=True,
                    )

            if candidate is None and (gap_diag is None or int(gap_diag.get("gcd_match_count") or 0) == 0):
                candidate = _resolve_comicvine_candidate(session, barcode=normalized)

            if candidate is None:
                gap_reason = _scanner_gap_finish_reason(gap_diag or {})
                session.add(item)
                session.flush()
                final_status = ITEM_NEEDS_REVIEW
                _log_scanner_barcode_gap(
                    item_id=item_id,
                    scanner_barcode=normalized,
                    local_catalog_hit=local_catalog_hit,
                    p106_called=p106_called,
                    diagnosis=gap_diag,
                    final_scanner_status=final_status,
                )
                return _finish(session, item, status=final_status, reason=gap_reason)

        if local_full_barcode and barcode_catalog_identity_conflict(session, normalized):
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason="Multiple catalog records conflict for this UPC — pick the correct issue.",
            )

        prefix_reason = publisher_validation_for_match(
            normalized,
            publisher=candidate.get("publisher"),
            issue_number=candidate.get("issue_number"),
            year=candidate.get("year"),
        )
        if prefix_reason:
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=f"Publisher prefix guard: {prefix_reason}",
            )

        # Store the validated candidate + apply it to the item.
        _clear_candidates(session, item_id)
        _add_candidate(
            session,
            item_id=item_id,
            source=str(candidate["source"]),
            rank=0,
            data={**candidate, "score": candidate.get("confidence", 0.0)},
        )
        item.match_source = str(candidate["source"])
        item.confidence = float(candidate.get("confidence") or 0.0)
        item.selected_catalog_issue_id = candidate.get("catalog_issue_id")
        item.selected_variant_id = candidate.get("variant_id")
        item.matched_publisher = (candidate.get("publisher") or None)
        item.matched_series = (candidate.get("series") or None)
        item.matched_issue_number = (candidate.get("issue_number") or None)
        item.matched_year = (candidate.get("year") or None)
        item.cover_url = (candidate.get("cover_url") or None)

        learned_row = candidate.get("learned_row")
        if isinstance(learned_row, ComicIssueBarcode):
            learned_row.times_seen += 1
            learned_row.updated_at = utc_now()
            session.add(learned_row)

        catalog_issue_id = candidate.get("catalog_issue_id")
        barcode_strong = is_validated_full_upc_exact_match(
            normalized,
            publisher=candidate.get("publisher"),
            issue_number=candidate.get("issue_number"),
            year=candidate.get("year"),
        )
        local_trusted = (
            local_full_barcode
            and is_local_trusted_match_source(str(candidate.get("source")))
            and catalog_issue_id is not None
            and barcode_strong
        )

        info_note = ""
        if local_trusted or (
            catalog_issue_id is not None
            and str(candidate.get("source")) in {MATCH_SOURCE_CATALOG_UPC, MATCH_SOURCE_LEARNED}
        ):
            ocr_supp = p105.ocr_supplement or p105.left_supplement_ocr or ""
            ocr_note = ocr_barcode_info_note(
                normalized_barcode=normalized,
                ocr_supplement=ocr_supp,
                matched_series=candidate.get("series"),
                matched_issue_number=candidate.get("issue_number"),
            )
            fp_outcome = evaluate_cover_fingerprint_vs_barcode(
                session,
                image_path=abs_path,
                catalog_issue_id=int(catalog_issue_id),
                barcode_validation_strong=barcode_strong,
                intake_item_id=int(item.id) if item.id is not None else None,
                final_issue_id=int(catalog_issue_id),
            )
            if fp_outcome.blocks_auto_match:
                return _finish(
                    session,
                    item,
                    status=ITEM_NEEDS_REVIEW,
                    reason=fp_outcome.info_message,
                )
            info_note = combine_info_notes(
                ocr_note,
                fingerprint_note_from_outcome(fp_outcome) if barcode_strong else None,
            ) or ""
        elif catalog_issue_id is not None and candidate["source"] == MATCH_SOURCE_CATALOG_UPC:
            cover_ok, cover_reason = _cover_confirms_barcode_match(
                session,
                image_path=abs_path,
                catalog_issue_id=int(catalog_issue_id),
                barcode_validation_strong=barcode_strong,
                intake_item_id=int(item.id) if item.id is not None else None,
            )
            if not cover_ok:
                item.confidence = min(item.confidence, 0.75)
                return _finish(
                    session,
                    item,
                    status=ITEM_NEEDS_REVIEW,
                    reason=f"Barcode match needs cover confirmation: {cover_reason}",
                )

        if p105_reason and not local_trusted and candidate["source"] == MATCH_SOURCE_CATALOG_UPC:
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=p105_reason,
            )

        if local_trusted:
            final_status = ITEM_AUTO_MATCHED
            finish_reason = info_note or None
        else:
            final_status = (
                ITEM_AUTO_MATCHED
                if candidate["source"] in {MATCH_SOURCE_LEARNED, MATCH_SOURCE_CATALOG_UPC}
                else ITEM_READY_FOR_REVIEW
            )
            finish_reason = None
        return _finish(session, item, status=final_status, reason=finish_reason)
    except Exception as exc:  # noqa: BLE001
        logger.exception("intake.item.failed item_id=%s", item_id)
        return _fail(session, item, f"Processing error: {exc}")


def _finish(session: Session, item: IntakeSessionItem, *, status: str, reason: str | None) -> str:
    if item.normalized_barcode:
        _stamp_item_barcode_identity(item, item.normalized_barcode)
    item.status = status
    item.reason = reason
    item.processed_at = utc_now()
    session.add(item)
    session.commit()
    logger.info("intake.item.done item_id=%s status=%s", item.id, status)
    return status


def _fail(session: Session, item: IntakeSessionItem, message: str) -> str:
    item.status = ITEM_FAILED
    item.error = message
    item.processed_at = utc_now()
    session.add(item)
    session.commit()
    return ITEM_FAILED


def run_intake_item_async(item_id: int) -> None:
    """Spawn a daemon thread that processes one item in its own DB session."""

    def _runner() -> None:
        from app.db.session import get_engine

        try:
            with Session(get_engine()) as bg_session:
                process_intake_item(bg_session, item_id=item_id)
        except Exception:
            logger.exception("intake.worker thread failed item_id=%s", item_id)

    thread = threading.Thread(target=_runner, name=f"intake-item-{item_id}", daemon=True)
    thread.start()
