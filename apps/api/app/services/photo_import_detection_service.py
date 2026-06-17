"""P100 detection reads + confirm/reject."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.acquisition import ACQUISITION_TYPE_OTHER
from app.models.photo_import import (
    DETECTION_STATUS_CONFIRMED,
    DETECTION_STATUS_REJECTED,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportSession,
)
from app.schemas.acquisition import AcquisitionCreatePayload, AddBooksItem, AddBooksPayload
from app.schemas.photo_import import (
    PhotoImportCandidateRead,
    PhotoImportConfirmPayload,
    PhotoImportConfirmResponse,
    PhotoImportDetectedBookRead,
)
from app.services.acquisition.acquisition_inventory_service import add_catalog_issues
from app.services.acquisition.acquisition_service import create_acquisition
from app.services.photo_import_session_service import (
    assert_session_owner,
    get_session_by_token_or_404,
    refresh_session_counts,
    session_to_read,
)


def candidate_to_read(row: PhotoImportCandidate) -> PhotoImportCandidateRead:
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
        release_date=row.release_date,
        match_score=float(row.match_score),
        match_reason=row.match_reason,
        rank=int(row.rank),
    )


def detection_to_read(session: Session, row: PhotoImportDetectedBook) -> PhotoImportDetectedBookRead:
    best = session.exec(
        select(PhotoImportCandidate)
        .where(PhotoImportCandidate.detected_book_id == row.id)
        .order_by(PhotoImportCandidate.rank.asc())
    ).first()
    return PhotoImportDetectedBookRead(
        id=int(row.id or 0),
        session_id=int(row.session_id),
        image_id=int(row.image_id),
        crop_path=row.crop_path,
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
        ai_variant_hint=row.ai_variant_hint,
        ai_cover_year=row.ai_cover_year,
        ai_confidence=row.ai_confidence,
        ai_reason=row.ai_reason,
        best_candidate=candidate_to_read(best) if best else None,
    )


def list_session_detections(session: Session, *, token: str, owner_user_id: int) -> list[PhotoImportDetectedBookRead]:
    import_row = get_session_by_token_or_404(session, token=token)
    assert_session_owner(import_row, owner_user_id=owner_user_id)
    rows = session.exec(
        select(PhotoImportDetectedBook)
        .where(PhotoImportDetectedBook.session_id == import_row.id)
        .order_by(PhotoImportDetectedBook.id.asc())
    ).all()
    return [detection_to_read(session, row) for row in rows]


def list_detection_candidates(
    session: Session,
    *,
    owner_user_id: int,
    detection_id: int,
) -> list[PhotoImportCandidateRead]:
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
    return [candidate_to_read(row) for row in rows]


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
    det.confidence = max(float(det.confidence), float(cand.match_score) / 100.0)
    session.add(det)
    session.commit()
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
    if det.selected_catalog_issue_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select a catalog match first")
    det.status = DETECTION_STATUS_CONFIRMED
    session.add(det)
    session.commit()
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
        items.append(
            AddBooksItem(
                catalog_issue_id=item.catalog_issue_id,
                quantity=item.quantity,
            )
        )
        det.status = DETECTION_STATUS_CONFIRMED
        det.selected_catalog_issue_id = item.catalog_issue_id
        det.selected_variant_id = item.variant_id
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
