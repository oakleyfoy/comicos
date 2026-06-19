"""P100 detection reads + confirm/reject."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.acquisition import ACQUISITION_TYPE_OTHER
from app.models.photo_import import (
    CAPTURE_MODE_SINGLE_COMIC,
    DETECTION_STATUS_CONFIRMED,
    DETECTION_STATUS_REJECTED,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
)
from app.services.photo_import_candidate_cover_service import cover_urls_for_photo_import_candidates
from app.services.photo_import_crop_service import crop_api_path, resolve_crop_abs_path
from app.services.photo_import_learning_service import record_photo_import_confirmation
from app.schemas.acquisition import AcquisitionCreatePayload, AddBooksItem, AddBooksPayload
from app.schemas.photo_import import (
    PhotoImportCandidateDebugInfo,
    PhotoImportCandidateRead,
    PhotoImportConfirmPayload,
    PhotoImportConfirmResponse,
    PhotoImportDetectedBookRead,
    PhotoImportDetectionCandidatesResponse,
)
from app.services.acquisition.acquisition_inventory_service import add_catalog_issues
from app.services.acquisition.acquisition_service import create_acquisition
from app.services.photo_import_candidate_service import (
    candidate_debug_info,
    catalog_candidate_matches_vision,
    vision_identification_label,
)
from app.services.photo_import_review_rules import can_confirm_detection, qualifies_for_bulk_high_confidence_confirm
from app.services.photo_import_session_service import (
    assert_session_owner,
    get_session_by_token_or_404,
    normalize_capture_mode,
    refresh_session_counts,
)
from app.services.photo_import_storage_service import (
    resolve_photo_import_storage_path,
    source_image_api_path,
)


def candidate_to_read(row: PhotoImportCandidate) -> PhotoImportCandidateRead:
    breakdown = row.score_breakdown or {}
    return PhotoImportCandidateRead(
        id=int(row.id or 0),
        detected_book_id=int(row.detected_book_id),
        catalog_issue_id=int(row.catalog_issue_id),
        variant_id=row.variant_id,
        publisher=row.publisher,
        series=row.series,
        issue_number=row.issue_number,
        variant_name=row.variant_name,
        cover_url=row.cover_url,
        thumbnail_url=row.thumbnail_url or row.cover_url,
        release_date=row.release_date,
        match_score=float(row.match_score),
        match_reason=row.match_reason,
        matched_on=row.matched_on,
        rank=int(row.rank),
        base_text_score=breakdown.get("base_text_score"),
        cover_similarity_score=breakdown.get("cover_similarity_score"),
        fingerprint_score=breakdown.get("fingerprint_score"),
        barcode_score=breakdown.get("barcode_score"),
        final_score=breakdown.get("final_score") or float(row.match_score),
        visual_score_status=breakdown.get("visual_score_status"),
        visual_match_label=breakdown.get("visual_match_label"),
    )


def _best_candidate(session: Session, detection_id: int) -> PhotoImportCandidate | None:
    return session.exec(
        select(PhotoImportCandidate)
        .where(PhotoImportCandidate.detected_book_id == detection_id)
        .order_by(PhotoImportCandidate.rank.asc())
    ).first()


def _selected_candidate(session: Session, det: PhotoImportDetectedBook) -> PhotoImportCandidate | None:
    if det.selected_catalog_issue_id is None:
        return None
    return session.exec(
        select(PhotoImportCandidate)
        .where(
            PhotoImportCandidate.detected_book_id == det.id,
            PhotoImportCandidate.catalog_issue_id == det.selected_catalog_issue_id,
        )
        .order_by(PhotoImportCandidate.rank.asc())
    ).first()


def _display_image_url(session: Session, det: PhotoImportDetectedBook) -> str | None:
    if det.status != DETECTION_STATUS_CONFIRMED or det.selected_catalog_issue_id is None:
        return None
    covers = cover_urls_for_photo_import_candidates(session, issue_ids=[int(det.selected_catalog_issue_id)])
    return covers.get(int(det.selected_catalog_issue_id))


def _catalog_verification_fields(
    row: PhotoImportDetectedBook,
    best: PhotoImportCandidate | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """vision_label, status (verified|disagrees|unmatched), catalog_label, disagreement_reason, legacy_reason."""
    vision_label = vision_identification_label(row)
    if vision_label is None:
        return None, None, None, None, _verification_reason_legacy(row, best)

    if best is None:
        legacy = f"Vision identified {vision_label}; no catalog match found"
        return vision_label, "unmatched", None, None, legacy

    catalog_label = f"{best.series} #{best.issue_number}".strip()
    if catalog_candidate_matches_vision(row, series=best.series, issue_number=best.issue_number):
        legacy = f"Vision identified {vision_label}; catalog verified {catalog_label}"
        return vision_label, "verified", catalog_label, None, legacy

    breakdown = best.score_breakdown or {}
    evidence: list[str] = []
    if float(breakdown.get("barcode_score") or 0) >= 100:
        evidence.append("Barcode")
    if float(breakdown.get("fingerprint_score") or 0) >= 50:
        evidence.append("fingerprint")
    if float(breakdown.get("cover_similarity_score") or 0) >= 50:
        evidence.append("cover similarity")
    override = str(breakdown.get("override_reason") or "").strip()
    if override == "barcode" and "Barcode" not in evidence:
        evidence.insert(0, "Barcode")
    elif override == "fingerprint" and "fingerprint" not in evidence:
        evidence.append("fingerprint")
    elif override == "cover_similarity" and "cover similarity" not in evidence:
        evidence.append("cover similarity")
    disagree_reason = " / ".join(evidence) if evidence else "OCR or text match only (weak)"
    legacy = (
        f"Vision identified {vision_label}; catalog disagrees {catalog_label} "
        f"({disagree_reason})"
    )
    return vision_label, "disagrees", catalog_label, disagree_reason, legacy


def _verification_reason_legacy(
    row: PhotoImportDetectedBook,
    best: PhotoImportCandidate | None,
) -> str | None:
    """Human-readable summary of the vision guess and catalog verification result."""
    series = (row.ai_series or row.ai_visible_title_text or "").strip()
    issue = (row.ai_issue_number or "").strip()
    label = f"{series} #{issue}".strip() if issue else series
    alternates = [str(a).strip() for a in (row.ai_alternate_titles or []) if str(a).strip()]
    if best is not None:
        breakdown = best.score_breakdown or {}
        if float(breakdown.get("barcode_score") or 0) >= 100:
            return f"Barcode confirms issue: {best.series} #{best.issue_number}"
        visual = str(breakdown.get("visual_match_label") or "")
        if visual in {"Cover match", "Fingerprint match"}:
            return f"{visual} confirms issue: {best.series} #{best.issue_number}"
        if label:
            return f"Vision identified {label}; catalog match found ({best.series} #{best.issue_number})"
        return f"Catalog match found: {best.series} #{best.issue_number}"
    if alternates:
        return f"Vision uncertain: possible {' or '.join(alternates[:3])}"
    if label:
        return f"Vision guessed {label}; no catalog match found"
    return None


def detection_to_read(
    session: Session,
    row: PhotoImportDetectedBook,
    *,
    session_token: str | None = None,
) -> PhotoImportDetectedBookRead:
    best = _best_candidate(session, int(row.id or 0))
    (
        vision_label,
        catalog_status,
        catalog_label,
        catalog_disagree_reason,
        verification_reason,
    ) = _catalog_verification_fields(row, best)
    can_confirm = can_confirm_detection(row, best_candidate=best)
    has_candidates = int(row.candidate_count) > 0
    # needs_match: catalog genuinely has nothing to offer. needs_selection: candidates exist, user must pick.
    needs_match = not has_candidates
    if can_confirm:
        review_status = "ready"
    elif has_candidates:
        review_status = "needs_selection"
    else:
        review_status = "needs_match"
    crop_url = crop_api_path(detection_id=int(row.id or 0)) if resolve_crop_abs_path(row.crop_path) else None
    display_url = _display_image_url(session, row)

    recognition_source: str | None = None
    display_crop = False
    source_url: str | None = None
    import_row = session.get(PhotoImportSession, int(row.session_id))
    single_comic = import_row is not None and normalize_capture_mode(import_row.capture_mode) == CAPTURE_MODE_SINGLE_COMIC
    if single_comic:
        recognition_source = "full_image"
        display_crop = True
    image = session.get(PhotoImportImage, int(row.image_id))
    if session_token and image is not None:
        abs_original = resolve_photo_import_storage_path(image.storage_path, image_id=int(image.id or 0))
        if abs_original.is_file():
            source_url = source_image_api_path(session_token=session_token, image_id=int(image.id or 0))

    return PhotoImportDetectedBookRead(
        id=int(row.id or 0),
        session_id=int(row.session_id),
        image_id=int(row.image_id),
        crop_path=row.crop_path,
        crop_image_url=crop_url,
        display_image_url=display_url,
        source_image_url=source_url,
        recognition_source=recognition_source,
        display_crop=display_crop,
        bbox_x=row.bbox_x,
        bbox_y=row.bbox_y,
        bbox_width=row.bbox_width,
        bbox_height=row.bbox_height,
        status=row.status,
        recognition_status=row.recognition_status,
        candidate_count=int(row.candidate_count),
        selected_catalog_issue_id=row.selected_catalog_issue_id,
        selected_variant_id=row.selected_variant_id,
        confidence=float(row.confidence),
        ai_series=row.ai_series,
        ai_issue_number=row.ai_issue_number,
        ai_publisher=row.ai_publisher,
        ai_subtitle_guess=row.ai_subtitle_guess,
        ai_variant_hint=row.ai_variant_hint,
        ai_variant_guess=row.ai_variant_guess,
        ai_cover_year=row.ai_cover_year,
        ai_visible_title_text=row.ai_visible_title_text,
        ai_visible_issue_text=row.ai_visible_issue_text,
        ai_visible_publisher_text=row.ai_visible_publisher_text,
        ai_visible_character_text=row.ai_visible_character_text,
        ai_uncertainty_reason=row.ai_uncertainty_reason,
        ai_alternate_titles=row.ai_alternate_titles,
        ai_confidence=row.ai_confidence,
        ai_reason=row.ai_reason,
        can_confirm=can_confirm,
        needs_match=needs_match,
        review_status=review_status,
        best_candidate=candidate_to_read(best) if best else None,
        recognition_mode=getattr(row, "recognition_mode", None),
        ai_barcode=getattr(row, "ai_barcode", None),
        verification_reason=verification_reason,
        vision_identification_label=vision_label,
        catalog_verification_status=catalog_status,
        catalog_verification_label=catalog_label,
        catalog_disagreement_reason=catalog_disagree_reason,
    )


def list_session_detections(session: Session, *, token: str) -> list[PhotoImportDetectedBookRead]:
    """List detections for a session. Access is gated by the session token (QR / review link)."""
    import_row = get_session_by_token_or_404(session, token=token)
    rows = session.exec(
        select(PhotoImportDetectedBook)
        .where(PhotoImportDetectedBook.session_id == import_row.id)
        .order_by(PhotoImportDetectedBook.id.asc())
    ).all()
    return [detection_to_read(session, row, session_token=token) for row in rows]


def list_detection_candidates_debug(
    session: Session,
    *,
    owner_user_id: int,
    detection_id: int,
) -> PhotoImportDetectionCandidatesResponse:
    det = session.get(PhotoImportDetectedBook, detection_id)
    if det is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    if int(det.user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    rows = session.exec(
        select(PhotoImportCandidate)
        .where(PhotoImportCandidate.detected_book_id == detection_id)
        .order_by(PhotoImportCandidate.rank.asc())
    ).all()
    debug_raw = candidate_debug_info(session, detected_book_id=detection_id)
    selected = _selected_candidate(session, det)
    return PhotoImportDetectionCandidatesResponse(
        detection=detection_to_read(session, det),
        candidates=[candidate_to_read(row) for row in rows],
        selected_candidate=candidate_to_read(selected) if selected else None,
        debug=PhotoImportCandidateDebugInfo(
            search_terms_used=list(debug_raw.get("search_terms_used") or []),
            candidate_count=int(debug_raw.get("candidate_count") or 0),
            best_match_score=float(debug_raw.get("best_match_score") or 0),
            match_input=dict(debug_raw.get("match_input") or {}),
        ),
    )


def select_candidate(
    session: Session,
    *,
    owner_user_id: int,
    detection_id: int,
    candidate_id: int,
) -> PhotoImportDetectedBookRead:
    det = session.get(PhotoImportDetectedBook, detection_id)
    if det is None or int(det.user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    cand = session.get(PhotoImportCandidate, candidate_id)
    if cand is None or int(cand.detected_book_id) != detection_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    det.selected_catalog_issue_id = int(cand.catalog_issue_id)
    det.selected_variant_id = cand.variant_id
    session.add(det)
    session.commit()
    rows = session.exec(
        select(PhotoImportCandidate)
        .where(PhotoImportCandidate.detected_book_id == detection_id)
        .order_by(PhotoImportCandidate.rank.asc())
    ).all()
    record_photo_import_confirmation(
        session,
        det=det,
        candidate_rankings=[(int(r.catalog_issue_id), float(r.match_score)) for r in rows],
    )
    session.refresh(det)
    return detection_to_read(session, det)


def reject_detection(session: Session, *, owner_user_id: int, detection_id: int) -> PhotoImportDetectedBookRead:
    det = session.get(PhotoImportDetectedBook, detection_id)
    if det is None or int(det.user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    det.status = DETECTION_STATUS_REJECTED
    session.add(det)
    session.commit()
    refresh_session_counts(session, session_id=int(det.session_id))
    session.refresh(det)
    return detection_to_read(session, det)


def confirm_detection(session: Session, *, owner_user_id: int, detection_id: int) -> PhotoImportDetectedBookRead:
    det = session.get(PhotoImportDetectedBook, detection_id)
    if det is None or int(det.user_id) != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detection not found")
    best = _best_candidate(session, detection_id)
    if not can_confirm_detection(det, best_candidate=best):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select a catalog match first")
    det.status = DETECTION_STATUS_CONFIRMED
    session.add(det)
    session.commit()
    rows = session.exec(
        select(PhotoImportCandidate)
        .where(PhotoImportCandidate.detected_book_id == detection_id)
        .order_by(PhotoImportCandidate.rank.asc())
    ).all()
    record_photo_import_confirmation(
        session,
        det=det,
        candidate_rankings=[(int(r.catalog_issue_id), float(r.match_score)) for r in rows],
    )
    session.refresh(det)
    return detection_to_read(session, det)


def _ensure_session_acquisition(session: Session, import_row: PhotoImportSession) -> int:
    if import_row.acquisition_id:
        return int(import_row.acquisition_id)
    acq = create_acquisition(
        session,
        owner_user_id=int(import_row.user_id),
        payload=AcquisitionCreatePayload(
            acquisition_type=ACQUISITION_TYPE_OTHER,
            purchase_date=date.today(),
            seller_name="Photo Import",
            notes="Photo Import session",
        ),
    )
    import_row.acquisition_id = int(acq.id)
    session.add(import_row)
    session.commit()
    return int(acq.id)


def confirm_session_books(
    session: Session,
    *,
    owner_user_id: int,
    token: str,
    payload: PhotoImportConfirmPayload,
) -> PhotoImportConfirmResponse:
    import_row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(import_row, owner_user_id=owner_user_id)
    acquisition_id = _ensure_session_acquisition(session, import_row)

    items: list[AddBooksItem] = []
    for item in payload.items:
        det = session.get(PhotoImportDetectedBook, item.detected_book_id)
        if det is None or int(det.session_id) != int(import_row.id or 0):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid detection id")
        best = _best_candidate(session, int(det.id or 0))
        if not can_confirm_detection(det, best_candidate=best):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Detection {item.detected_book_id} requires a selected catalog match",
            )
        catalog_id = int(det.selected_catalog_issue_id or item.catalog_issue_id)
        items.append(
            AddBooksItem(
                catalog_issue_id=catalog_id,
                quantity=item.quantity,
            )
        )
        det.status = DETECTION_STATUS_CONFIRMED
        det.selected_catalog_issue_id = catalog_id
        det.selected_variant_id = item.variant_id or det.selected_variant_id
        session.add(det)

    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No items to confirm")

    result = add_catalog_issues(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        payload=AddBooksPayload(items=items),
    )
    copy_ids: list[int] = []
    for r in result.results:
        copy_ids.extend([int(i) for i in r.inventory_copy_ids])
    import_row.confirmed_count += len(copy_ids)
    session.add(import_row)
    session.commit()
    refresh_session_counts(session, session_id=int(import_row.id or 0))
    return PhotoImportConfirmResponse(
        acquisition_id=acquisition_id,
        inventory_copy_ids=copy_ids,
        confirmed_count=len(copy_ids),
    )


def list_high_confidence_confirmable_detection_ids(
    session: Session,
    *,
    token: str,
    owner_user_id: int,
) -> list[int]:
    import_row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(import_row, owner_user_id=owner_user_id)
    rows = session.exec(
        select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.session_id == import_row.id)
    ).all()
    ids: list[int] = []
    for det in rows:
        if det.status in {DETECTION_STATUS_CONFIRMED, DETECTION_STATUS_REJECTED}:
            continue
        best = _best_candidate(session, int(det.id or 0))
        if qualifies_for_bulk_high_confidence_confirm(det, best_candidate=best):
            ids.append(int(det.id or 0))
    return ids
