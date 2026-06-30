"""Async intake queue API: hands-free capture + separate review/identification."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models import User
from app.models.intake_queue import IntakeSession, IntakeSessionItem
from app.services.acquisition.acquisition_service import acquisition_display_label
from app.schemas.intake_queue import (
    IntakeAddAllResponse,
    IntakeCatalogSearchResponse,
    IntakeCatalogSearchResult,
    IntakeChooseIssuePayload,
    IntakeCounts,
    IntakeEnqueueResponse,
    IntakeItemCandidateRead,
    IntakeItemRead,
    IntakeReviewResponse,
    IntakeSessionCreatePayload,
    IntakeSessionRead,
    IntakeSessionStatusPayload,
)
from app.services.intake_queue_service import (
    accept_intake_item,
    add_all_high_confidence,
    add_intake_item_to_inventory,
    assert_owner,
    candidates_for_item,
    choose_intake_item_issue,
    create_intake_session,
    enqueue_intake_item,
    get_intake_session_by_token_or_404,
    import_and_accept_intake_item,
    intake_counts,
    list_intake_items,
    reject_intake_item,
    requeue_intake_item,
    search_catalog_issues,
    set_session_status,
    attach_full_cover_photo_to_intake_item,
)
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.barcode_scan_consensus_service import suggest_corrected_barcode
from app.services.intake_api_review_response_log_service import log_intake_item_api_response

logger = logging.getLogger(__name__)

intake_router = APIRouter(prefix="/api/v1/intake", tags=["Intake Queue"])


def attach_intake_queue_layer(app: FastAPI) -> None:
    app.include_router(intake_router)


def _session_urls(token: str) -> tuple[str, str]:
    base = get_settings().frontend_url.rstrip("/")
    scanner = f"{base}/intake/scan/{token}" if base else f"/intake/scan/{token}"
    review = f"{base}/intake/review/{token}" if base else f"/intake/review/{token}"
    return scanner, review


def _session_to_read(db: Session, row: IntakeSession) -> IntakeSessionRead:
    scanner, review = _session_urls(row.session_token)
    acquisition_label: str | None = None
    if row.acquisition_id:
        from app.models import Acquisition

        acq = db.get(Acquisition, int(row.acquisition_id))
        if acq is not None:
            acquisition_label = acquisition_display_label(acq)
    return IntakeSessionRead(
        id=int(row.id or 0),
        session_token=row.session_token,
        name=row.name,
        status=row.status,
        source_device=row.source_device,
        scanned_count=int(row.scanned_count),
        acquisition_id=row.acquisition_id,
        acquisition_label=acquisition_label,
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_seen_at=row.last_seen_at,
        scanner_url=scanner,
        review_url=review,
    )


def _item_image_url(token: str, item_id: int) -> str:
    return f"/api/v1/intake/sessions/{token}/items/{item_id}/image"


def _item_to_read(session: Session, item: IntakeSessionItem, *, token: str) -> IntakeItemRead:
    db_candidates = list(candidates_for_item(session, item_id=int(item.id or 0)))
    candidates = [
        IntakeItemCandidateRead(
            id=int(c.id or 0),
            catalog_issue_id=c.catalog_issue_id,
            variant_id=c.variant_id,
            publisher=c.publisher,
            series=c.series,
            issue_number=c.issue_number,
            cover_url=c.cover_url,
            score=float(c.score),
            source=c.source,
            rank=int(c.rank),
        )
        for c in db_candidates
    ]
    barcode_read: dict | None = None
    if item.barcode_read_json:
        try:
            parsed = json.loads(item.barcode_read_json)
            if isinstance(parsed, dict):
                barcode_read = parsed
        except json.JSONDecodeError:
            barcode_read = None
    log_intake_item_api_response(item, db_candidates=db_candidates, barcode_read=barcode_read)

    gap = barcode_read.get("barcode_gap") if isinstance(barcode_read, dict) else None
    gap_tops = gap.get("needs_review_top_candidates") if isinstance(gap, dict) else None
    barcode_gap_candidates_count = len(gap_tops) if isinstance(gap_tops, list) else 0
    full_cover_image_path = (
        str(barcode_read.get("full_cover_storage_path") or "")
        if isinstance(barcode_read, dict)
        else ""
    )
    logger.info(
        "REVIEW_PAYLOAD_SOURCE %s",
        json.dumps(
            {
                "item_id": int(item.id or 0),
                "status": item.status,
                "barcode_gap_candidates_count": barcode_gap_candidates_count,
                "db_intake_item_candidate_count": len(db_candidates),
                "rendered_candidates_count": len(candidates),
                "using_full_cover_path": bool(full_cover_image_path),
                "full_cover_image_path": full_cover_image_path,
            }
        ),
    )
    return IntakeItemRead(
        id=int(item.id or 0),
        session_id=int(item.session_id),
        status=item.status,
        confidence=float(item.confidence),
        match_source=item.match_source,
        raw_barcode=item.raw_barcode,
        normalized_barcode=item.normalized_barcode,
        base_upc=item.base_upc,
        extension=item.extension,
        possible_corrected_barcode=(
            suggest_corrected_barcode(item.raw_barcode or "")
            if item.raw_barcode
            else None
        ),
        barcode_read=barcode_read,
        selected_catalog_issue_id=item.selected_catalog_issue_id,
        selected_variant_id=item.selected_variant_id,
        matched_publisher=item.matched_publisher,
        matched_series=item.matched_series,
        matched_issue_number=item.matched_issue_number,
        matched_year=item.matched_year,
        cover_url=item.cover_url,
        reason=item.reason,
        error=item.error,
        image_url=_item_image_url(token, int(item.id or 0)),
        acquisition_id=item.acquisition_id,
        inventory_copy_id=item.inventory_copy_id,
        created_at=item.created_at,
        processed_at=item.processed_at,
        candidates=candidates,
    )


# --- session lifecycle ---
@intake_router.post("/sessions", response_model=IntakeSessionRead)
def create_session_endpoint(
    payload: IntakeSessionCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeSessionRead:
    row = create_intake_session(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=payload.acquisition_id,
        source_device=payload.source_device,
        name=payload.name,
    )
    return _session_to_read(session, row)


@intake_router.get("/sessions/{token}", response_model=IntakeSessionRead)
def get_session_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> IntakeSessionRead:
    row = get_intake_session_by_token_or_404(session, token=token)
    return _session_to_read(session, row)


@intake_router.post("/sessions/{token}/status", response_model=IntakeSessionRead)
def set_status_endpoint(
    token: str,
    payload: IntakeSessionStatusPayload,
    session: Session = Depends(get_session),
) -> IntakeSessionRead:
    row = set_session_status(session, token=token, new_status=payload.status)
    return _session_to_read(session, row)


# --- capture (non-blocking, token-based so the phone needs no login) ---
@intake_router.post("/sessions/{token}/items", response_model=IntakeEnqueueResponse)
async def enqueue_item_endpoint(
    token: str,
    file: UploadFile = File(...),
    raw_barcode: str | None = Form(default=None),
    frame_files: list[UploadFile] | None = File(default=None),
    session: Session = Depends(get_session),
) -> IntakeEnqueueResponse:
    item = await enqueue_intake_item(
        session,
        token=token,
        upload=file,
        raw_barcode=raw_barcode,
        frame_uploads=frame_files or [],
    )
    row = get_intake_session_by_token_or_404(session, token=token)
    return IntakeEnqueueResponse(
        item_id=int(item.id or 0),
        status=item.status,
        scanned_count=int(row.scanned_count),
    )


@intake_router.get("/sessions/{token}/counts", response_model=IntakeCounts)
def counts_endpoint(
    token: str,
    session: Session = Depends(get_session),
) -> IntakeCounts:
    row = get_intake_session_by_token_or_404(session, token=token)
    return IntakeCounts(**intake_counts(session, session_id=int(row.id or 0)))


@intake_router.get("/sessions/{token}/items/{item_id}/image")
def item_image_endpoint(
    token: str,
    item_id: int,
    session: Session = Depends(get_session),
) -> FileResponse:
    row = get_intake_session_by_token_or_404(session, token=token)
    item = session.get(IntakeSessionItem, item_id)
    if item is None or int(item.session_id) != int(row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake item not found")
    abs_path = resolve_photo_import_storage_path(item.storage_path, image_id=item_id)
    if not abs_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    return FileResponse(abs_path, media_type=item.mime_type or "image/jpeg")


# --- review (owner) ---
@intake_router.get("/sessions/{token}/review", response_model=IntakeReviewResponse)
def review_endpoint(
    token: str,
    status_filter: str | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeReviewResponse:
    row = get_intake_session_by_token_or_404(session, token=token)
    assert_owner(row, owner_user_id=int(current_user.id))
    items = list_intake_items(session, session_id=int(row.id or 0), status_filter=status_filter)
    return IntakeReviewResponse(
        session=_session_to_read(session, row),
        counts=IntakeCounts(**intake_counts(session, session_id=int(row.id or 0))),
        items=[_item_to_read(session, it, token=token) for it in items],
    )


def _item_response(session: Session, item: IntakeSessionItem) -> IntakeItemRead:
    intake = session.get(IntakeSession, int(item.session_id))
    token = intake.session_token if intake else ""
    return _item_to_read(session, item, token=token)


@intake_router.post("/items/{item_id}/accept", response_model=IntakeItemRead)
def accept_item_endpoint(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = accept_intake_item(session, item_id=item_id, owner_user_id=int(current_user.id))
    return _item_response(session, item)


@intake_router.post("/items/{item_id}/choose", response_model=IntakeItemRead)
def choose_item_endpoint(
    item_id: int,
    payload: IntakeChooseIssuePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = choose_intake_item_issue(
        session,
        item_id=item_id,
        owner_user_id=int(current_user.id),
        catalog_issue_id=payload.catalog_issue_id,
        variant_id=payload.variant_id,
    )
    return _item_response(session, item)


@intake_router.post("/items/{item_id}/import-and-accept", response_model=IntakeItemRead)
def import_and_accept_endpoint(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = import_and_accept_intake_item(session, item_id=item_id, owner_user_id=int(current_user.id))
    return _item_response(session, item)


@intake_router.get("/catalog-search", response_model=IntakeCatalogSearchResponse)
def catalog_search_endpoint(
    q: str,
    issue_number: str | None = None,
    limit: int = 25,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeCatalogSearchResponse:
    rows = search_catalog_issues(session, query=q, issue_number=issue_number, limit=limit)
    return IntakeCatalogSearchResponse(
        results=[IntakeCatalogSearchResult(**row) for row in rows]
    )


@intake_router.post("/items/{item_id}/add-to-inventory", response_model=IntakeItemRead)
def add_to_inventory_endpoint(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = add_intake_item_to_inventory(session, item_id=item_id, owner_user_id=int(current_user.id))
    return _item_response(session, item)


@intake_router.post("/items/{item_id}/reject", response_model=IntakeItemRead)
def reject_item_endpoint(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = reject_intake_item(session, item_id=item_id, owner_user_id=int(current_user.id))
    return _item_response(session, item)


@intake_router.post("/items/{item_id}/requeue", response_model=IntakeItemRead)
def requeue_item_endpoint(
    item_id: int,
    full_cover_required: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = requeue_intake_item(
        session,
        item_id=item_id,
        owner_user_id=int(current_user.id),
        full_cover_required=full_cover_required,
    )
    return _item_response(session, item)


@intake_router.post("/items/{item_id}/full-cover-photo", response_model=IntakeItemRead)
async def full_cover_photo_endpoint(
    item_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeItemRead:
    item = await attach_full_cover_photo_to_intake_item(
        session,
        item_id=item_id,
        owner_user_id=int(current_user.id),
        upload=file,
    )
    return _item_response(session, item)


@intake_router.post(
    "/sessions/{token}/items/{item_id}/full-cover-photo",
    response_model=IntakeItemRead,
)
async def session_full_cover_photo_endpoint(
    token: str,
    item_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> IntakeItemRead:
    """Token-authed full-cover upload for the phone hand-off (no login required).

    The desktop review page shows a QR/link that opens this item on the owner's
    phone; the phone captures the cover with its camera and POSTs it here. The
    session token is the auth boundary (same as enqueue), and the owner is derived
    from the session, so we never expose another user's items.
    """
    row = get_intake_session_by_token_or_404(session, token=token)
    item = session.get(IntakeSessionItem, item_id)
    if item is None or int(item.session_id) != int(row.id or 0):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intake item not found")
    item = await attach_full_cover_photo_to_intake_item(
        session,
        item_id=item_id,
        owner_user_id=int(row.user_id),
        upload=file,
    )
    return _item_response(session, item)


@intake_router.post("/sessions/{token}/add-all-high-confidence", response_model=IntakeAddAllResponse)
def add_all_endpoint(
    token: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntakeAddAllResponse:
    result = add_all_high_confidence(session, token=token, owner_user_id=int(current_user.id))
    return IntakeAddAllResponse(**result)
