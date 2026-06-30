"""Background identification worker for the async intake queue.

Each queued ``IntakeSessionItem`` is processed independently and asynchronously so the
phone scanner never blocks. Identification order favors instant/high-confidence sources:

    1. Learned barcode map (``comic_issue_barcodes``) — instant from prior accepts.
    2. Local catalog UPC table (``catalog_upc``).
    3. ComicVine on-demand lookup (needs review before inventory).

Local catalog misses trigger P106 GCD barcode lookup, then P106.1 metadata recovery when GCD
has no barcode on file, then ComicVine. Unique exact GCD matches may auto-import/attach so the
scanner never shows a blank identity.

Every candidate is run through safe-match validation so we never auto-match the wrong book.
"""

from __future__ import annotations

import json
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
    ITEM_NEEDS_FULL_COVER_PHOTO,
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
    merge_comic_upc_decodes,
    normalize_upc,
    upc_check_digit_valid,
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
from app.services.intake_scanner_barcode_authority_service import (
    PARTIAL_BARCODE_REASON,
    barcode_decode_review_reason,
    comic_barcode_scan_is_partial,
    mark_partial_barcode_in_read_json,
    p105_field_test_snapshot,
    p106_gap_is_exact_barcode_authority,
    sync_intake_display_from_p106_gap,
    try_resolve_seventeen_digit_barcode_from_p105,
)
from app.services.photo_import_upc_barcode_decoder import (
    collect_raw_upc_candidates_from_pil,
    decode_upc_from_image_bytes,
)
from app.services.photo_import_fingerprint_service import fingerprint_match_score_for_crop_path
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.recognition.catalog_matcher import load_catalog_issue_identity
from app.services.scanner_barcode_field_test_service import (
    ScannerBarcodeResolutionTrace,
    log_scanner_p106_gcd_miss,
    probe_local_barcode_hits,
    record_scanner_barcode_resolution,
)

logger = logging.getLogger(__name__)

# Unique exact GCD barcode hits auto-resolve during scan (no manual CLI).
AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP = True

_active_barcode_traces: dict[int, ScannerBarcodeResolutionTrace] = {}

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


def _clear_fingerprint_artifacts(
    session: Session,
    *,
    item_id: int,
    gap_diag: dict[str, Any] | None,
) -> int:
    """Discard fingerprint review artifacts once a barcode source resolves the issue.

    Deletes persisted ``IntakeItemCandidate(source="fingerprint")`` rows and strips
    fingerprint review keys from the gap diagnosis so they cannot survive (or be
    re-persisted) alongside a successful barcode match. Returns the number of
    fingerprint candidate rows deleted.
    """
    deleted = 0
    rows = session.exec(
        select(IntakeItemCandidate).where(IntakeItemCandidate.item_id == item_id)
    ).all()
    for row in rows:
        if str(getattr(row, "source", "") or "") == "fingerprint":
            session.delete(row)
            deleted += 1
    if isinstance(gap_diag, dict):
        for key in (
            "needs_review_top_candidates",
            "fingerprint_review",
            "review_decision",
            "review_candidates",
            "fingerprint_candidates",
        ):
            gap_diag.pop(key, None)
    return deleted


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


def _begin_barcode_trace(item: IntakeSessionItem) -> ScannerBarcodeResolutionTrace:
    item_id = int(item.id or 0)
    trace = ScannerBarcodeResolutionTrace(
        intake_item_id=item_id,
        session_id=int(item.session_id) if item.session_id is not None else None,
    )
    _active_barcode_traces[item_id] = trace
    return trace


def _pop_barcode_trace(item_id: int | None) -> ScannerBarcodeResolutionTrace | None:
    if item_id is None:
        return None
    return _active_barcode_traces.pop(int(item_id), None)


def _scanner_gap_finish_reason(diagnosis: dict[str, Any]) -> str:
    from app.services.intake_full_cover_followup_service import FULL_COVER_USER_MESSAGE

    if diagnosis.get("needs_full_cover_photo"):
        return FULL_COVER_USER_MESSAGE
    tops = diagnosis.get("needs_review_top_candidates")
    if isinstance(tops, list) and tops:
        if diagnosis.get("review_decision") == "needs_review_top_candidates":
            return "Cover fingerprint suggests catalog match(es) — review top candidates or use Import & Accept."
    cv = diagnosis.get("comicvine_review_candidate")
    if isinstance(cv, dict) and cv.get("import_ready"):
        return "ComicVine and cover fingerprint agree — use Import & Accept to add to your catalog."
    if diagnosis.get("ready_to_auto_import"):
        return "Not in your catalog yet — GCD match found (Import & Accept to add)."
    if diagnosis.get("status") in {"review_required", "conflict"}:
        return "GCD barcode match needs review — pick the issue or use Import & Accept."
    if int(diagnosis.get("gcd_match_count") or 0) == 0:
        if int(diagnosis.get("gcd_sql_exact_barcode_column_count") or 0) > 0:
            return "GCD barcode exists in database but P106 could not attach — use Import & Accept or ops review."
        return "Not in your catalog yet — use Import & Accept (ComicVine) or pick the issue."
    return "Not in your catalog yet — use Import & Accept or pick the issue."


def _apply_p106_diagnosis_to_intake_item(item: IntakeSessionItem, *, gap_diag: dict[str, Any]) -> None:
    from app.services.p106_barcode_gap_resolver_service import (
        apply_barcode_gap_display_to_intake_item,
        merge_barcode_gap_into_barcode_read,
    )

    item.barcode_read_json = merge_barcode_gap_into_barcode_read(item.barcode_read_json, gap_diag)
    from app.services.intake_full_cover_followup_service import merge_full_cover_flags_into_barcode_read

    item.barcode_read_json = merge_full_cover_flags_into_barcode_read(
        item.barcode_read_json,
        gap_diag=gap_diag,
    )
    apply_barcode_gap_display_to_intake_item(item, gap_diag)


def _gcd_has_exact_barcode_authority(gcd_path: Path, normalized: str) -> bool:
    from app.services.gcd_barcode_search_service import find_gcd_rows_by_normalized_barcode

    if not gcd_path.is_file():
        return False
    lookup_key = normalize_scan_preserving_supplement(normalized) or normalize_upc(normalized)
    return bool(find_gcd_rows_by_normalized_barcode(gcd_path, lookup_key))


def _intake_supplement_frame_bytes(*, image_path: Path) -> list[bytes]:
    """Extra JPEG frames captured after barcode detect (``{stem}_f0.jpg``, …)."""
    frames: list[bytes] = []
    for path in sorted(image_path.parent.glob(f"{image_path.stem}_f*.jpg")):
        if not path.is_file():
            continue
        try:
            frames.append(path.read_bytes())
        except OSError:
            logger.debug("intake.barcode.supplement_frame_read_failed path=%s", path, exc_info=True)
    return frames


def _merge_seventeen_digit_from_image_frames(*, main: str, frame_bytes_list: list[bytes]) -> str | None:
    """Merge 12-digit main UPC with EAN-5 / supplement strings from one or more photos."""
    main_norm = normalize_upc(main)
    if len(main_norm) != 12:
        return None
    candidates: list[str] = [main_norm]
    try:
        import io as io_mod

        from PIL import Image
    except ImportError:
        Image = None  # type: ignore[misc, assignment]

    for fb in frame_bytes_list:
        if not fb:
            continue
        decoded = decode_upc_from_image_bytes(fb)
        if decoded:
            candidates.append(decoded[0])
        if Image is None:
            continue
        try:
            with Image.open(io_mod.BytesIO(fb)) as img:
                candidates.extend(collect_raw_upc_candidates_from_pil(img.convert("RGB")))
        except Exception:
            logger.debug("intake.barcode.frame_candidate_collect_failed", exc_info=True)
    merged = merge_comic_upc_decodes(candidates)
    merged_norm = normalize_upc(merged or "")
    if len(merged_norm) >= 17 and merged_norm.startswith(main_norm):
        return merged_norm[:17]
    return None


def _recover_seventeen_digit_barcode(
    *,
    normalized: str,
    p105: Any,
    image_bytes: bytes,
    supplement_frame_bytes: list[bytes] | None = None,
) -> str | None:
    recovered = try_resolve_seventeen_digit_barcode_from_p105(normalized=normalized, p105=p105)
    if recovered:
        return recovered
    main = normalize_upc(p105.main_upc or normalized)
    if len(main) != 12:
        return None
    frames: list[bytes] = [image_bytes]
    for fb in supplement_frame_bytes or []:
        if fb and fb not in frames:
            frames.append(fb)
    merged_from_frames = _merge_seventeen_digit_from_image_frames(main=main, frame_bytes_list=frames)
    if merged_from_frames:
        return merged_from_frames
    return None


def _apply_recovered_barcode_to_item(item: IntakeSessionItem, *, normalized: str) -> None:
    item.normalized_barcode = normalized[:64]
    item.base_upc = base_upc(normalized)[:16]
    item.extension = supplement_extension(normalized) or None
    _stamp_item_barcode_identity(item, normalized)


def _drop_local_candidate_if_gcd_identity_differs(
    session: Session,
    *,
    candidate: dict[str, Any] | None,
    normalized: str,
    gcd_path: Path,
    cache_path: Path,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Unique GCD barcode hit overrides a stale local catalog_upc / learned mapping."""
    if candidate is None or len(normalize_upc(normalized)) < 17:
        return candidate, None
    if not _gcd_has_exact_barcode_authority(gcd_path, normalized):
        return candidate, None

    from app.services.gcd_barcode_search_service import find_gcd_rows_by_normalized_barcode

    gcd_rows = find_gcd_rows_by_normalized_barcode(gcd_path, normalized)
    gcd_series = (str(gcd_rows[0].get("series") or "") if gcd_rows else "").strip().lower()
    catalog_issue_id = candidate.get("catalog_issue_id")
    if gcd_series and catalog_issue_id is not None:
        identity = load_catalog_issue_identity(session, int(catalog_issue_id))
        local_series = (identity.series if identity else candidate.get("series") or "").strip().lower()
        if local_series and gcd_series != local_series:
            logger.warning(
                "intake.barcode.local_candidate_overridden barcode=%s local_series=%s gcd_series=%s issue_id=%s",
                normalized,
                local_series,
                gcd_series,
                catalog_issue_id,
            )
            gap_diag = {
                "gcd_match_count": len(gcd_rows),
                "exact_barcode_path": True,
                "gcd_matches": gcd_rows,
                "ready_to_auto_import": len(gcd_rows) == 1,
            }
            return None, gap_diag
    return candidate, None


def _p106_reports_no_gcd_match(gap_diag: dict[str, Any] | None) -> bool:
    return gap_diag is None or int(gap_diag.get("gcd_match_count") or 0) == 0


def _should_run_p106_1_non_barcode_recovery(
    *,
    normalized: str,
    gap_diag: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> bool:
    """Run P106.1 when P106 found no attachable GCD barcode match and local catalog missed."""
    if candidate is not None:
        return False
    if len(normalize_upc(normalized)) < 17:
        return False
    if gap_diag is not None and int(gap_diag.get("gcd_match_count") or 0) > 0:
        return False
    if gap_diag is not None and gap_diag.get("p106_1_skipped"):
        return False
    return True


def _intake_full_cover_followup_gate(
    *,
    gap_diag: dict[str, Any] | None,
    primary_region: Any,
    recognition_region: Any,
    item: IntakeSessionItem,
    local_catalog_hit: bool,
    p106_exact_barcode_authority: bool,
    normalized: str,
    using_full_cover_recognition: bool = False,
) -> tuple[bool, bool]:
    """Return (full_cover_followup_required, skip_fingerprint_search)."""
    from app.services.intake_full_cover_followup_service import (
        gcd_barcode_lookup_missed,
        intake_has_full_cover_followup_image,
        require_full_cover_before_fingerprint_review,
        should_require_full_cover_followup,
    )

    has_full_cover_image = intake_has_full_cover_followup_image(item) or using_full_cover_recognition
    unsafe_fingerprint_region = not recognition_region.fingerprint_region_safe or (
        not primary_region.fingerprint_region_safe and not has_full_cover_image
    )
    barcode_path_miss = (
        gcd_barcode_lookup_missed(gap_diag or {})
        and bool(normalized)
        and not local_catalog_hit
        and not p106_exact_barcode_authority
    )
    full_cover_required = should_require_full_cover_followup(
        gap_diag=gap_diag,
        primary_region=primary_region,
        recognition_region=recognition_region,
        has_full_cover_image=has_full_cover_image,
        local_catalog_hit=local_catalog_hit,
        p106_exact_barcode_authority=p106_exact_barcode_authority,
        barcode_decoded=bool(normalized),
    )
    if require_full_cover_before_fingerprint_review(
        normalized=normalized,
        candidate=None,
        local_catalog_hit=local_catalog_hit,
        p106_exact_barcode_authority=p106_exact_barcode_authority,
        gap_diag=gap_diag,
        recognition_region=recognition_region,
        has_full_cover_followup_image=has_full_cover_image,
    ):
        full_cover_required = True
    if barcode_path_miss and (full_cover_required or unsafe_fingerprint_region) and not has_full_cover_image:
        full_cover_required = True
    skip_fp = full_cover_required or not recognition_region.fingerprint_region_safe
    return full_cover_required, skip_fp


def _fingerprint_review_candidate_count(tops: Any) -> int:
    if not isinstance(tops, list):
        return 0
    n = 0
    for row in tops:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "fingerprint") == "fingerprint":
            n += 1
    return n


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

    trace = _begin_barcode_trace(item)

    from app.services.intake_p106_1_execution_trace_service import (
        activate_intake_p106_1_trace,
        format_execution_trace,
        log_p106_1_after_suppression,
        set_fingerprint_search_gate,
    )

    _p106_1_trace_cm = activate_intake_p106_1_trace(item_id)
    _p106_1_exec_trace = _p106_1_trace_cm.__enter__()
    try:
        abs_path = resolve_photo_import_storage_path(item.storage_path, image_id=item_id)
        if not abs_path.is_file():
            return _fail(session, item, "Captured image is missing from storage.")
        image_bytes = abs_path.read_bytes()

        from app.services.intake_full_cover_followup_service import resolve_intake_recognition_image_path

        recognition_path, using_full_cover_followup = resolve_intake_recognition_image_path(item, abs_path)
        recognition_bytes = image_bytes
        if recognition_path.resolve() != abs_path.resolve():
            recognition_bytes = recognition_path.read_bytes()

        too_small, img_w, img_h, small_reason = recognition_image_too_small(recognition_bytes)
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

        supplement_frame_bytes = _intake_supplement_frame_bytes(image_path=abs_path)
        known_main = normalize_upc(item.raw_barcode or item.normalized_barcode or "")
        if len(known_main) != 12 or not upc_check_digit_valid(known_main):
            known_main = ""
        p105 = read_comic_barcode_from_image_bytes(
            image_bytes,
            session=session,
            cover_path=abs_path,
            intake_item_id=item_id,
            log_context=f"intake item_id={item_id}",
            supplement_frame_bytes=supplement_frame_bytes,
            known_main_upc=known_main or None,
        )
        item.barcode_read_json = p105.to_json()

        import io as io_mod

        from PIL import Image

        from app.services.intake_fingerprint_image_region_service import (
            assess_fingerprint_image_region,
            barcode_crop_jpeg_bytes,
            merge_fingerprint_region_instrumentation,
        )
        from app.services.p105_comic_barcode_regions import compute_barcode_region_geometry

        def _geometry_from_bytes(raw: bytes):
            with Image.open(io_mod.BytesIO(raw)) as pil:
                return compute_barcode_region_geometry(pil.convert("RGB"))

        primary_geometry = _geometry_from_bytes(image_bytes)
        recognition_geometry = (
            _geometry_from_bytes(recognition_bytes)
            if recognition_bytes is not image_bytes
            else primary_geometry
        )
        primary_region = assess_fingerprint_image_region(
            abs_path,
            image_bytes=image_bytes,
            geometry=primary_geometry,
        )
        recognition_region = assess_fingerprint_image_region(
            recognition_path,
            image_bytes=recognition_bytes,
            geometry=recognition_geometry,
            force_full_cover=using_full_cover_followup,
        )

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
        trace.scanned_barcode_raw = item.raw_barcode
        trace.normalized_barcode = normalized
        _p106_1_exec_trace.barcode = normalized
        trace.p105_snapshot = p105_field_test_snapshot(p105)

        recovered_full = _recover_seventeen_digit_barcode(
            normalized=normalized,
            p105=p105,
            image_bytes=image_bytes,
            supplement_frame_bytes=supplement_frame_bytes,
        )
        if recovered_full and len(normalize_upc(normalized)) < 17:
            scan_validation = validate_single_barcode_read(recovered_full)
            if scan_validation.acceptance != "rejected_checksum":
                normalized = scan_validation.normalized or recovered_full[:64]
                _apply_recovered_barcode_to_item(item, normalized=normalized)
                trace.normalized_barcode = normalized
                _p106_1_exec_trace.barcode = normalized
                logger.info(
                    "intake.item.barcode_recovered item_id=%s normalized=%s",
                    item_id,
                    normalized,
                )

        if comic_barcode_scan_is_partial(normalized=normalized, p105=p105):
            extraction = extract_barcode_from_image(
                image_bytes,
                allow_gpt_fallback=True,
                log_context=f"intake item_id={item_id} partial_gpt",
            )
            gpt_code = (extraction.get("barcode") or "").strip()
            gpt_norm = normalize_upc(gpt_code)
            if len(gpt_norm) >= 17 and gpt_norm.startswith(normalize_upc(normalized)[:12]):
                scan_validation = validate_single_barcode_read(gpt_norm)
                if scan_validation.acceptance != "rejected_checksum":
                    normalized = scan_validation.normalized or gpt_norm[:64]
                    _apply_recovered_barcode_to_item(item, normalized=normalized)
                    trace.normalized_barcode = normalized
                    item.barcode_read_json = p105.to_json()
                    logger.info(
                        "intake.item.barcode_gpt_recovered item_id=%s normalized=%s method=%s",
                        item_id,
                        normalized,
                        extraction.get("method"),
                    )
            if comic_barcode_scan_is_partial(normalized=normalized, p105=p105):
                trace.partial_barcode = True
                item.barcode_read_json = mark_partial_barcode_in_read_json(item.barcode_read_json)
                return _finish(
                    session,
                    item,
                    status=ITEM_NEEDS_REVIEW,
                    reason=PARTIAL_BARCODE_REASON,
                )

        from app.services.gcd_catalog_import_dashboard_service import resolve_gcd_path

        gcd_path_for_decode = resolve_gcd_path(None)
        decode_review = barcode_decode_review_reason(
            p105=p105,
            normalized=normalized,
            gcd_path=gcd_path_for_decode,
        )
        if decode_review:
            trace.decode_review_reason = decode_review
            return _finish(session, item, status=ITEM_NEEDS_REVIEW, reason=decode_review)

        learned_probe, upc_probe = probe_local_barcode_hits(session, normalized_barcode=normalized)
        trace.learned_barcode_hit = learned_probe
        trace.local_catalog_upc_hit = upc_probe

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

        # 12-digit-only when a full UPC+5 is required (prefix list + GCD variants).
        if direct_market_requires_supplement_key(normalized, gcd_path=gcd_path_for_decode):
            trace.partial_barcode = True
            item.barcode_read_json = mark_partial_barcode_in_read_json(item.barcode_read_json)
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=PARTIAL_BARCODE_REASON,
            )

        candidate = _resolve_local_catalog_candidate(session, barcode=normalized)
        local_catalog_hit = candidate is not None
        gap_diag: dict[str, Any] | None = None
        gap_diag_error: str | None = None
        p106_exact_barcode_authority = False
        p106_1_attempted = False

        from app.services.gcd_catalog_import_dashboard_service import resolve_cache_path, resolve_gcd_path

        gcd_path = resolve_gcd_path(None)
        cache_path = resolve_cache_path(None)
        if not gcd_path.is_file() and len(normalize_upc(normalized)) >= 17:
            logger.error("intake.gcd_database_missing path=%s item_id=%s barcode=%s", gcd_path, item_id, normalized)
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=(
                    f"GCD catalog database is missing on this server ({gcd_path}). "
                    "Scans cannot auto-import until ops restores it."
                ),
            )

        candidate, pre_gap_diag = _drop_local_candidate_if_gcd_identity_differs(
            session,
            candidate=candidate,
            normalized=normalized,
            gcd_path=gcd_path,
            cache_path=cache_path,
        )
        if pre_gap_diag is not None:
            gap_diag = pre_gap_diag
            local_catalog_hit = candidate is not None
            if p106_gap_is_exact_barcode_authority(gap_diag):
                p106_exact_barcode_authority = True
                sync_intake_display_from_p106_gap(item, gap_diag)

        if candidate is None:
            from app.services.p105_barcode_repair_service import record_missing_barcode_queue
            from app.services.p106_barcode_gap_resolver_service import (
                diagnose_barcode_gap,
                resolve_barcode_gap,
                should_auto_resolve_barcode_gap_on_scan,
            )

            record_missing_barcode_queue(session, item=item)
            trace.p106_called = True
            p106_1_attempted = False
            if gap_diag is None or (
                _p106_reports_no_gcd_match(gap_diag) and _gcd_has_exact_barcode_authority(gcd_path, normalized)
            ):
                try:
                    gap_diag = diagnose_barcode_gap(
                        session,
                        barcode=normalized,
                        gcd_path=gcd_path,
                        cache_path=cache_path,
                    )
                except Exception as exc:
                    gap_diag_error = str(exc)
                    logger.warning(
                        "p106.barcode_gap.diagnose_failed item_id=%s barcode=%s gcd_path=%s",
                        item_id,
                        normalized,
                        gcd_path,
                        exc_info=True,
                    )

            if gap_diag is not None:
                trace.apply_p106_diagnosis(gap_diag, gcd_path=gcd_path)
                if p106_gap_is_exact_barcode_authority(gap_diag):
                    p106_exact_barcode_authority = True
                    sync_intake_display_from_p106_gap(item, gap_diag)
                try:
                    _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                except Exception:
                    logger.warning(
                        "p106.barcode_gap.display_failed item_id=%s barcode=%s",
                        item_id,
                        normalized,
                        exc_info=True,
                    )

            if _p106_reports_no_gcd_match(gap_diag):
                log_scanner_p106_gcd_miss(
                    item_id=int(item_id),
                    normalized_barcode=normalized,
                    diagnosis=gap_diag,
                    gcd_path=gcd_path,
                    diagnose_error=gap_diag_error,
                )

            if _p106_reports_no_gcd_match(gap_diag) and _gcd_has_exact_barcode_authority(gcd_path, normalized):
                try:
                    gap_diag = diagnose_barcode_gap(
                        session,
                        barcode=normalized,
                        gcd_path=gcd_path,
                        cache_path=cache_path,
                    )
                    trace.apply_p106_diagnosis(gap_diag, gcd_path=gcd_path)
                    try:
                        _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                    except Exception:
                        logger.warning(
                            "p106.barcode_gap.display_failed item_id=%s barcode=%s retry=1",
                            item_id,
                            normalized,
                            exc_info=True,
                        )
                except Exception:
                    logger.warning(
                        "p106.barcode_gap.diagnose_retry_failed item_id=%s barcode=%s",
                        item_id,
                        normalized,
                        exc_info=True,
                    )

            # --- ComicVine barcode lookup is a BARCODE source. It MUST run before any
            # fingerprint recovery so that a barcode match always wins and visual
            # fingerprint matching is never shown alongside a resolved barcode. ---
            comicvine_attempted = False
            if (
                candidate is None
                and _p106_reports_no_gcd_match(gap_diag)
                and not p106_exact_barcode_authority
                and not p106_gap_is_exact_barcode_authority(gap_diag or {})
                and not _gcd_has_exact_barcode_authority(gcd_path, normalized)
                and not (gap_diag and gap_diag.get("ready_to_auto_import"))
            ):
                comicvine_attempted = True
                trace.comicvine_fallback_called = True
                candidate = _resolve_comicvine_candidate(session, barcode=normalized)
                if candidate is not None:
                    logger.info(
                        "intake.comicvine_barcode_resolved item_id=%s barcode=%s",
                        item_id,
                        normalized,
                    )

            # --- If ANY barcode source (local / learned / GCD / ComicVine) resolved the
            # issue, discard fingerprint review artifacts and skip P106 fingerprint
            # recovery entirely before continuing the normal barcode import flow. ---
            if candidate is not None:
                cleared_fp = _clear_fingerprint_artifacts(
                    session, item_id=int(item.id or 0), gap_diag=gap_diag
                )
                if gap_diag:
                    try:
                        _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                    except Exception:
                        logger.warning(
                            "intake.barcode_source_won.display_failed item_id=%s",
                            item_id,
                            exc_info=True,
                        )
                logger.info(
                    "intake.barcode_source_won item_id=%s source=%s comicvine_attempted=%s "
                    "cleared_fingerprint_rows=%s",
                    item_id,
                    candidate.get("source"),
                    comicvine_attempted,
                    cleared_fp,
                )

            p106_1_attempted = False
            if candidate is None and _should_run_p106_1_non_barcode_recovery(
                normalized=normalized,
                gap_diag=gap_diag,
                candidate=candidate,
            ):
                from app.services.p106_1_gcd_non_barcode_recovery_service import (
                    P106_1_RECOVERY_STAGE,
                    build_p106_1_intake_hint_snapshot,
                    enrich_gap_diagnosis_with_gcd_non_barcode_recovery,
                )

                p106_1_attempted = True
                full_cover_precheck, skip_fp_search = _intake_full_cover_followup_gate(
                    gap_diag=gap_diag,
                    primary_region=primary_region,
                    recognition_region=recognition_region,
                    item=item,
                    local_catalog_hit=local_catalog_hit,
                    p106_exact_barcode_authority=p106_exact_barcode_authority,
                    normalized=normalized,
                    using_full_cover_recognition=using_full_cover_followup,
                )
                set_fingerprint_search_gate(
                    skip_fingerprint_search=skip_fp_search,
                    full_cover_followup_required=full_cover_precheck,
                    fingerprint_region_safe=recognition_region.fingerprint_region_safe,
                    fingerprint_image_region=recognition_region.fingerprint_image_region,
                )
                recovery_hints, hint_snapshot = build_p106_1_intake_hint_snapshot(
                    session,
                    item=item,
                    barcode=normalized,
                    image_path=recognition_path,
                    image_bytes=recognition_bytes,
                    p105=p105,
                    full_cover_followup_required=full_cover_precheck,
                    fingerprint_region_safe=recognition_region.fingerprint_region_safe,
                    fingerprint_image_region=recognition_region.fingerprint_image_region,
                )
                logger.info(
                    "p106_1.intake_hints_before_enrich %s",
                    json.dumps(hint_snapshot, default=str),
                )

                gap_diag = enrich_gap_diagnosis_with_gcd_non_barcode_recovery(
                    session,
                    item=item,
                    barcode=normalized,
                    gcd_path=gcd_path,
                    cache_path=cache_path,
                    image_path=recognition_path,
                    image_bytes=recognition_bytes,
                    prior_diagnosis=gap_diag or {},
                    p105=p105,
                    recovery_hints=recovery_hints,
                )
                trace.apply_p106_1_from_diagnosis(gap_diag, gcd_path=gcd_path)
                if gap_diag.get("recovery_stage") == P106_1_RECOVERY_STAGE:
                    trace.p106_called = True
                    block = gap_diag.get("recovery_block_reason") or gap_diag.get("recovery_reason")
                    if block:
                        logger.info(
                            "p106_1.intake_outcome item_id=%s barcode=%s ready=%s block=%s status=%s",
                            item_id,
                            normalized,
                            gap_diag.get("ready_to_auto_import"),
                            block,
                            gap_diag.get("status"),
                        )
                    try:
                        _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                    except Exception:
                        logger.warning(
                            "p106_1.non_barcode.display_failed item_id=%s barcode=%s",
                            item_id,
                            normalized,
                            exc_info=True,
                        )

            if gap_diag and AUTO_RESOLVE_UNIQUE_GCD_BARCODE_GAP and should_auto_resolve_barcode_gap_on_scan(gap_diag):
                try:
                    resolve_outcome = resolve_barcode_gap(
                        session,
                        barcode=normalized,
                        gcd_path=gcd_path,
                        cache_path=cache_path,
                        confirm_write=True,
                        intake_item_id=int(item.id or 0),
                        diagnosis=gap_diag if gap_diag.get("ready_to_auto_import") else None,
                    )
                    trace.apply_p106_resolve_outcome(resolve_outcome)
                    result = resolve_outcome.get("result") or {}
                    resolved_issue_id = result.get("catalog_issue_id")
                    if resolved_issue_id is not None and candidate is None:
                        candidate = _local_candidate(
                            session,
                            source=MATCH_SOURCE_CATALOG_UPC,
                            catalog_issue_id=int(resolved_issue_id),
                            variant_id=result.get("variant_id"),
                        )
                    if candidate is None:
                        candidate = _resolve_local_catalog_candidate(session, barcode=normalized)
                    local_catalog_hit = candidate is not None
                    if resolve_outcome.get("written"):
                        p106_exact_barcode_authority = True
                except Exception:
                    logger.warning(
                        "p106.barcode_gap.auto_resolve_failed item_id=%s barcode=%s",
                        item_id,
                        normalized,
                        exc_info=True,
                    )
                # P106.1 GCD non-barcode recovery (OCR/metadata) just auto-resolved a
                # catalog/GCD issue: that barcode-equivalent match wins, so any
                # fingerprint review candidates produced during P106.1 are discarded.
                if candidate is not None:
                    cleared_fp = _clear_fingerprint_artifacts(
                        session, item_id=int(item.id or 0), gap_diag=gap_diag
                    )
                    if gap_diag:
                        try:
                            _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                        except Exception:
                            logger.warning(
                                "intake.barcode_source_won.display_failed item_id=%s",
                                item_id,
                                exc_info=True,
                            )
                    logger.info(
                        "intake.barcode_source_won item_id=%s source=%s stage=p106_1_auto_resolve "
                        "cleared_fingerprint_rows=%s",
                        item_id,
                        candidate.get("source"),
                        cleared_fp,
                    )

            if candidate is None and _p106_reports_no_gcd_match(gap_diag):
                if _gcd_has_exact_barcode_authority(gcd_path, normalized) or p106_gap_is_exact_barcode_authority(
                    gap_diag or {}
                ):
                    # GCD barcode authority wins: clear any fingerprint review artifacts.
                    _clear_fingerprint_artifacts(session, item_id=int(item.id or 0), gap_diag=gap_diag)
                    if gap_diag:
                        sync_intake_display_from_p106_gap(item, gap_diag)
                        try:
                            _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                        except Exception:
                            logger.warning(
                                "intake.barcode_authority.display_failed item_id=%s",
                                item_id,
                                exc_info=True,
                            )
                    gap_reason = _scanner_gap_finish_reason(gap_diag or {})
                    session.add(item)
                    session.flush()
                    return _finish(session, item, status=ITEM_NEEDS_REVIEW, reason=gap_reason)

            if candidate is None:
                if gap_diag:
                    from app.services.intake_full_cover_followup_service import (
                        FULL_COVER_USER_MESSAGE,
                        apply_full_cover_followup_to_diagnosis,
                        gcd_barcode_lookup_missed,
                        intake_has_full_cover_followup_image,
                        require_full_cover_before_fingerprint_review,
                        should_require_full_cover_followup,
                    )
                    from app.services.intake_p106_1_intake_debug_service import (
                        log_intake_fingerprint_review_instrumentation,
                        save_p106_1_intake_debug_bundle,
                    )
                    from app.services.p106_fingerprint_review_fallback_service import (
                        persist_review_candidates_on_intake_item,
                    )
                    from app.services.p106_barcode_gap_resolver_service import barcode_gap_payload_from_diagnosis

                    has_full_cover_image = intake_has_full_cover_followup_image(item) or using_full_cover_followup
                    unsafe_fingerprint_region = not recognition_region.fingerprint_region_safe or (
                        not primary_region.fingerprint_region_safe and not has_full_cover_image
                    )
                    if unsafe_fingerprint_region:
                        gap_diag.pop("needs_review_top_candidates", None)
                        gap_diag.pop("fingerprint_review", None)
                        gap_diag.pop("review_decision", None)
                        merge_fingerprint_region_instrumentation(gap_diag, recognition_region)

                    tops = gap_diag.get("needs_review_top_candidates")
                    review_count = len(tops) if isinstance(tops, list) else 0
                    barcode_path_miss = (
                        gcd_barcode_lookup_missed(gap_diag)
                        and bool(normalized)
                        and not local_catalog_hit
                        and not p106_exact_barcode_authority
                    )
                    full_cover_required = should_require_full_cover_followup(
                        gap_diag=gap_diag,
                        primary_region=primary_region,
                        recognition_region=recognition_region,
                        has_full_cover_image=has_full_cover_image,
                        local_catalog_hit=local_catalog_hit,
                        p106_exact_barcode_authority=p106_exact_barcode_authority,
                        barcode_decoded=bool(normalized),
                    )
                    if barcode_path_miss and (full_cover_required or unsafe_fingerprint_region) and not has_full_cover_image:
                        full_cover_required = True
                    if require_full_cover_before_fingerprint_review(
                        normalized=normalized,
                        candidate=candidate,
                        local_catalog_hit=local_catalog_hit,
                        p106_exact_barcode_authority=p106_exact_barcode_authority,
                        gap_diag=gap_diag,
                        recognition_region=recognition_region,
                        has_full_cover_followup_image=has_full_cover_image,
                    ):
                        full_cover_required = True
                        gap_diag.pop("needs_review_top_candidates", None)
                        gap_diag.pop("fingerprint_review", None)
                        gap_diag.pop("review_decision", None)
                        _clear_fingerprint_artifacts(session, item_id=int(item.id or 0), gap_diag=gap_diag)

                    debug_payload: dict[str, Any] = {
                        "intake_item_id": item_id,
                        "barcode": normalized,
                        "item_status_intended": ITEM_NEEDS_FULL_COVER_PHOTO
                        if full_cover_required
                        else ITEM_NEEDS_REVIEW,
                        "recognition_image_path": str(recognition_path),
                        "fingerprint_image_path": str(recognition_path),
                        "primary_image_path": str(abs_path),
                        "full_cover_followup_required": full_cover_required,
                        "needs_full_cover_photo": full_cover_required,
                        "p106_1_called": p106_1_attempted,
                        "p106_1_review_candidates_count": review_count,
                        "barcode_gap": barcode_gap_payload_from_diagnosis(gap_diag),
                    }
                    merge_fingerprint_region_instrumentation(debug_payload, recognition_region)
                    debug_payload["primary_fingerprint_image_region"] = primary_region.fingerprint_image_region
                    debug_payload["primary_fingerprint_region_safe"] = primary_region.fingerprint_region_safe
                    log_intake_fingerprint_review_instrumentation(debug_payload)
                    try:
                        barcode_crop = barcode_crop_jpeg_bytes(image_bytes, primary_geometry)
                        save_p106_1_intake_debug_bundle(
                            intake_item_id=int(item_id),
                            primary_path=abs_path,
                            primary_bytes=image_bytes,
                            recognition_path=recognition_path,
                            recognition_bytes=recognition_bytes,
                            fingerprint_path=recognition_path,
                            barcode_crop_bytes=barcode_crop,
                            region_debug=debug_payload,
                        )
                    except Exception:
                        logger.warning(
                            "intake.p106_1_debug_bundle_failed item_id=%s",
                            item_id,
                            exc_info=True,
                        )

                    fp_review_count = _fingerprint_review_candidate_count(tops)
                    log_p106_1_after_suppression(
                        review_candidates_count=review_count,
                        fingerprint_candidates_count=fp_review_count,
                        final_status=ITEM_NEEDS_FULL_COVER_PHOTO
                        if full_cover_required
                        else ITEM_NEEDS_REVIEW,
                    )

                    if full_cover_required and barcode_path_miss:
                        apply_full_cover_followup_to_diagnosis(
                            gap_diag,
                            primary_region,
                            recognition_region=recognition_region,
                        )
                        _clear_fingerprint_artifacts(session, item_id=int(item.id or 0), gap_diag=gap_diag)
                        try:
                            _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                        except Exception:
                            logger.warning(
                                "intake.full_cover_followup.display_failed item_id=%s",
                                item_id,
                                exc_info=True,
                            )
                        session.add(item)
                        session.flush()
                        return _finish(
                            session,
                            item,
                            status=ITEM_NEEDS_FULL_COVER_PHOTO,
                            reason=FULL_COVER_USER_MESSAGE,
                        )

                    try:
                        persist_review_candidates_on_intake_item(
                            session,
                            item_id=int(item.id or 0),
                            diagnosis=gap_diag,
                            add_candidate_fn=_add_candidate,
                            clear_candidates_fn=_clear_candidates,
                        )
                        _apply_p106_diagnosis_to_intake_item(item, gap_diag=gap_diag)
                    except Exception:
                        logger.warning(
                            "intake.fingerprint_review.persist_failed item_id=%s",
                            item_id,
                            exc_info=True,
                        )
                gap_reason = _scanner_gap_finish_reason(gap_diag or {})
                session.add(item)
                session.flush()
                final_status = ITEM_NEEDS_REVIEW
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
        if prefix_reason and not p106_exact_barcode_authority:
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
        if gap_diag and p106_gap_is_exact_barcode_authority(gap_diag):
            sync_intake_display_from_p106_gap(item, gap_diag)
        trace.match_source = str(candidate.get("source"))
        learned_probe, upc_probe = probe_local_barcode_hits(session, normalized_barcode=normalized)
        trace.learned_barcode_hit = learned_probe
        trace.local_catalog_upc_hit = upc_probe

        learned_row = candidate.get("learned_row")
        if isinstance(learned_row, ComicIssueBarcode):
            learned_row.times_seen += 1
            learned_row.updated_at = utc_now()
            session.add(learned_row)

        catalog_issue_id = candidate.get("catalog_issue_id")
        barcode_strong = p106_exact_barcode_authority or is_validated_full_upc_exact_match(
            normalized,
            publisher=candidate.get("publisher"),
            issue_number=candidate.get("issue_number"),
            year=candidate.get("year"),
        )
        local_trusted = (
            local_full_barcode
            and is_local_trusted_match_source(str(candidate.get("source")))
            and catalog_issue_id is not None
            and (barcode_strong or p106_exact_barcode_authority)
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
                barcode_validation_strong=barcode_strong or p106_exact_barcode_authority,
                intake_item_id=int(item.id) if item.id is not None else None,
                final_issue_id=int(catalog_issue_id),
            )
            trace.fingerprint_top_issue_id = fp_outcome.fingerprint_issue_id
            trace.fingerprint_top_confidence = fp_outcome.fingerprint_confidence
            if fp_outcome.blocks_auto_match and not p106_exact_barcode_authority:
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
            if not p106_exact_barcode_authority:
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
    finally:
        logger.info(
            "P106_1_EXECUTION_TRACE item_id=%s\n%s",
            item_id,
            format_execution_trace(_p106_1_exec_trace),
        )
        _p106_1_trace_cm.__exit__(None, None, None)


def _finish(session: Session, item: IntakeSessionItem, *, status: str, reason: str | None) -> str:
    trace = _pop_barcode_trace(int(item.id) if item.id is not None else None)
    record_scanner_barcode_resolution(
        trace=trace,
        item=item,
        final_status=status,
        final_reason=reason,
    )
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
    trace = _pop_barcode_trace(int(item.id) if item.id is not None else None)
    record_scanner_barcode_resolution(
        trace=trace,
        item=item,
        final_status=ITEM_FAILED,
        final_reason=message,
    )
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
