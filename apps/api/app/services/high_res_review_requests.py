"""High-resolution Epson/flatbed review requests (deterministic persistence; never enqueues OCR/matching workflows)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import CoverImage, CoverImageOcrQualityAnalysis, HighResReviewRequest, ScanSession, ScanSessionItem
from app.models.asset_ledger import utc_now
from app.schemas.cover_images import CoverImageRead
from app.schemas.high_res_review_requests import (
    HighResReviewRequestCreatePayload,
    HighResReviewRequestListResponse,
    HighResReviewRequestRead,
    HighResReviewRequestStatsRead,
    HighResReviewRequestSummaryRead,
)
from app.schemas.scan_sessions import ScanSessionCreatePayload
from app.services.cover_images import (
    decode_cover_image_upload_bytes_optional,
    persist_cover_bytes_for_inventory_copy,
    serialize_cover_image_read,
    sha256_raw_bytes,
)
from app.services import scan_sessions as scan_sess

_TERMINAL_REQ = frozenset({"review_complete", "cancelled"})
_ATTACH_ELIGIBLE = frozenset({"pending"})


def _resolve_inventory_for_create(
    session: Session,
    *,
    owner_user_id: int,
    payload: HighResReviewRequestCreatePayload,
) -> tuple[int, int | None, int | None, int | None]:
    anchor_inv = payload.inventory_copy_id
    cov_hint = payload.source_cover_image_id
    item_pk = payload.source_scan_session_item_id
    qa_pk = payload.source_ocr_quality_analysis_id

    if item_pk is not None:
        if qa_pk is not None:
            raise HTTPException(status_code=400, detail="Cannot combine scan_session_item with OCR quality analysis")

        it = session.get(ScanSessionItem, int(item_pk))
        if it is None:
            raise HTTPException(status_code=404, detail="Scan session item not found")

        sess_parent = session.get(ScanSession, int(it.scan_session_id))
        if sess_parent is None or int(sess_parent.owner_user_id) != owner_user_id:
            raise HTTPException(status_code=400, detail="Scan session item out of scope for this owner")

        if it.inventory_copy_id is not None:
            inferred_inv = int(it.inventory_copy_id)
        elif it.cover_image_id is not None:
            cov_it = session.get(CoverImage, int(it.cover_image_id))
            if cov_it is None:
                raise HTTPException(status_code=400, detail="Cover context missing from scan session item")
            if cov_it.inventory_copy_id is None:
                raise HTTPException(status_code=400, detail="Scan session item cover is not anchored to inventory")
            inferred_inv = int(cov_it.inventory_copy_id)
        else:
            raise HTTPException(
                status_code=400,
                detail="scan_session_item must reference inventory_copy_id or cover_image_id for deterministic anchoring",
            )

        cov_to_store: int | None = None
        if cov_hint is not None:
            if it.cover_image_id is not None and int(it.cover_image_id) != int(cov_hint):
                raise HTTPException(status_code=400, detail="source_cover_image_id contradicts scan session linkage")
            scan_sess._assert_cover_owned(session, owner_user_id=owner_user_id, cover_image_id=int(cov_hint))
            cov_to_store = int(cov_hint)
        elif it.cover_image_id is not None:
            scan_sess._assert_cover_owned(session, owner_user_id=owner_user_id, cover_image_id=int(it.cover_image_id))
            cov_to_store = int(it.cover_image_id)

        if anchor_inv is not None and anchor_inv != inferred_inv:
            raise HTTPException(status_code=400, detail="inventory_copy_id contradicts scan session item anchor")

        scan_sess._assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=inferred_inv)

        return inferred_inv, cov_to_store, int(item_pk), None

    if qa_pk is not None:
        qa = session.get(CoverImageOcrQualityAnalysis, int(qa_pk))
        if qa is None:
            raise HTTPException(status_code=404, detail="OCR quality analysis not found")

        qa_cover_id = int(qa.cover_image_id)
        cov_q = session.get(CoverImage, qa_cover_id)
        if cov_q is None:
            raise HTTPException(status_code=400, detail="OCR quality row missing cover linkage")
        if cov_q.inventory_copy_id is None:
            raise HTTPException(status_code=400, detail="OCR quality anchor cover is not wired to inventory")

        inferred_inv = int(cov_q.inventory_copy_id)

        if cov_hint is not None and int(cov_hint) != qa_cover_id:
            raise HTTPException(status_code=400, detail="source_cover_image_id contradicts OCR quality row")

        cov_to_store = qa_cover_id
        if cov_hint is not None:
            scan_sess._assert_cover_owned(session, owner_user_id=owner_user_id, cover_image_id=int(cov_hint))
        scan_sess._assert_cover_owned(session, owner_user_id=owner_user_id, cover_image_id=qa_cover_id)

        if anchor_inv is not None and anchor_inv != inferred_inv:
            raise HTTPException(status_code=400, detail="inventory_copy_id contradicts OCR quality cover anchor")

        scan_sess._assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=inferred_inv)

        return inferred_inv, cov_to_store, None, int(qa_pk)

    if cov_hint is not None:
        cov = scan_sess._assert_cover_owned(session, owner_user_id=owner_user_id, cover_image_id=int(cov_hint))
        if cov.inventory_copy_id is None:
            raise HTTPException(status_code=400, detail="Source cover lacks inventory linkage")
        inferred_inv = int(cov.inventory_copy_id)

        if anchor_inv is not None and anchor_inv != inferred_inv:
            raise HTTPException(status_code=400, detail="inventory_copy_id contradicts source cover linkage")

        scan_sess._assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=inferred_inv)

        return inferred_inv, int(cov_hint), None, None

    riskish = payload.source_inventory_risk_type or payload.source_action_center_category
    if anchor_inv is None:
        if riskish:
            raise HTTPException(
                status_code=400,
                detail="inventory_copy_id required when escalating from inventory-risk or action-center context",
            )
        raise HTTPException(status_code=400, detail="Cannot resolve inventory anchor for high-res review request")

    inferred_inv = int(anchor_inv)
    scan_sess._assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=inferred_inv)

    return inferred_inv, None, None, None


def create_high_res_review_request(
    session: Session,
    *,
    owner_user_id: int,
    payload: HighResReviewRequestCreatePayload,
) -> HighResReviewRequestRead:
    inv_id, cov_to_store, sess_item_pk, qa_pk = _resolve_inventory_for_create(
        session,
        owner_user_id=owner_user_id,
        payload=payload,
    )

    now = utc_now()

    req = HighResReviewRequest(
        owner_user_id=owner_user_id,
        inventory_copy_id=inv_id,
        source_cover_image_id=cov_to_store,
        source_scan_session_item_id=sess_item_pk,
        source_ocr_quality_analysis_id=qa_pk,
        source_inventory_risk_type=(
            payload.source_inventory_risk_type.strip()[:80]
            if payload.source_inventory_risk_type
            else None
        ),
        source_action_center_category=(
            payload.source_action_center_category.strip()[:80]
            if payload.source_action_center_category
            else None
        ),
        attach_scan_session_id=None,
        attach_scan_session_item_id=None,
        high_res_cover_image_id=None,
        request_reason=payload.request_reason,
        status="pending",
        priority=payload.priority,
        notes=(payload.notes.strip()[:8000] if payload.notes else None),
        created_at=now,
        updated_at=now,
        completed_at=None,
    )
    session.add(req)
    session.commit()
    session.refresh(req)
    return _hydrate_review_read(session, req)


def _hydrate_review_read(session: Session, row: HighResReviewRequest) -> HighResReviewRequestRead:
    base = HighResReviewRequestRead.model_validate(row, from_attributes=True)

    cov_src_payload: CoverImageRead | None = None
    if row.source_cover_image_id is not None:
        cov = session.get(CoverImage, int(row.source_cover_image_id))
        if cov is not None:
            cov_src_payload = serialize_cover_image_read(session, cov)

    high_payload: CoverImageRead | None = None
    if row.high_res_cover_image_id is not None:
        h = session.get(CoverImage, int(row.high_res_cover_image_id))
        if h is not None:
            high_payload = serialize_cover_image_read(session, h)

    dumped = base.model_dump()
    dumped["source_cover_scan"] = cov_src_payload
    dumped["review_high_res_scan"] = high_payload
    return HighResReviewRequestRead.model_validate(dumped)


def _request_owned(session: Session, *, owner_user_id: int | None, request_id: int) -> HighResReviewRequest:
    row = session.get(HighResReviewRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="High-resolution review request not found")
    if owner_user_id is not None and int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="High-resolution review request not found")
    return row


def get_high_res_review_request_detail(
    session: Session,
    *,
    owner_user_id: int | None,
    request_id: int,
) -> HighResReviewRequestRead:
    return _hydrate_review_read(session, _request_owned(session, owner_user_id=owner_user_id, request_id=request_id))


def list_high_res_review_requests_owner(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int | None,
    status_filter: str | None,
    priority_filter: str | None,
    reason_filter: str | None,
    limit: int,
    offset: int,
) -> HighResReviewRequestListResponse:
    stmt = select(HighResReviewRequest).where(HighResReviewRequest.owner_user_id == owner_user_id)
    if inventory_copy_id is not None:
        stmt = stmt.where(HighResReviewRequest.inventory_copy_id == int(inventory_copy_id))
    if status_filter is not None:
        stmt = stmt.where(HighResReviewRequest.status == str(status_filter))
    if priority_filter is not None:
        stmt = stmt.where(HighResReviewRequest.priority == str(priority_filter))
    if reason_filter is not None:
        stmt = stmt.where(HighResReviewRequest.request_reason == str(reason_filter))
    stmt = stmt.order_by(HighResReviewRequest.updated_at.desc(), HighResReviewRequest.id.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return HighResReviewRequestListResponse(
        requests=[HighResReviewRequestSummaryRead.model_validate(r, from_attributes=True) for r in rows],
    )


def list_high_res_review_requests_ops(
    session: Session,
    *,
    owner_user_id_filter: int | None,
    inventory_copy_id: int | None,
    status_filter: str | None,
    priority_filter: str | None,
    reason_filter: str | None,
    limit: int,
    offset: int,
) -> HighResReviewRequestListResponse:
    stmt = select(HighResReviewRequest)
    if owner_user_id_filter is not None:
        stmt = stmt.where(HighResReviewRequest.owner_user_id == int(owner_user_id_filter))
    if inventory_copy_id is not None:
        stmt = stmt.where(HighResReviewRequest.inventory_copy_id == int(inventory_copy_id))
    if status_filter is not None:
        stmt = stmt.where(HighResReviewRequest.status == str(status_filter))
    if priority_filter is not None:
        stmt = stmt.where(HighResReviewRequest.priority == str(priority_filter))
    if reason_filter is not None:
        stmt = stmt.where(HighResReviewRequest.request_reason == str(reason_filter))
    stmt = stmt.order_by(HighResReviewRequest.updated_at.desc(), HighResReviewRequest.id.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return HighResReviewRequestListResponse(
        requests=[HighResReviewRequestSummaryRead.model_validate(r, from_attributes=True) for r in rows],
    )


def high_res_review_request_stats_owner(session: Session, *, owner_user_id: int) -> HighResReviewRequestStatsRead:
    stmt = (
        select(HighResReviewRequest.status, func.count(HighResReviewRequest.id))
        .where(HighResReviewRequest.owner_user_id == owner_user_id)
        .group_by(HighResReviewRequest.status)
    )
    rows_raw = session.exec(stmt).all()
    return HighResReviewRequestStatsRead(by_status={str(status): int(ct) for status, ct in rows_raw})

def high_res_review_request_stats_ops(session: Session) -> HighResReviewRequestStatsRead:
    stmt = select(HighResReviewRequest.status, func.count(HighResReviewRequest.id)).group_by(HighResReviewRequest.status)
    rows_raw = session.exec(stmt).all()
    return HighResReviewRequestStatsRead(by_status={str(status): int(ct) for status, ct in rows_raw})

def attach_high_res_review_scan_multipart(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    request_id: int,
    body: bytes,
    declared_content_type: str | None,
    source_filename: str | None,
) -> HighResReviewRequestRead:
    row = _request_owned(session, owner_user_id=owner_user_id, request_id=request_id)
    if row.status in _TERMINAL_REQ:
        raise HTTPException(status_code=400, detail="Cannot attach scan while request is terminal")
    if row.status not in _ATTACH_ELIGIBLE:
        raise HTTPException(status_code=400, detail="High-resolution scan ingestion is only allowed while pending")

    if row.high_res_cover_image_id is not None:
        raise HTTPException(status_code=400, detail="Deterministic ingest already retained a linked high-res scan")

    if not body:
        raise HTTPException(status_code=422, detail="Empty upload.")

    if len(body) > settings.cover_images_max_bytes:
        raise HTTPException(status_code=400, detail=f"Image exceeds ingest cap ({settings.cover_images_max_bytes} bytes)")

    decoded = decode_cover_image_upload_bytes_optional(body, declared_content_type)
    if decoded is None:
        raise HTTPException(status_code=400, detail="Unsupported or unreadable high-resolution scan payload")

    width_i, height_i, mime_i = decoded
    sha_hex = sha256_raw_bytes(body)

    now = utc_now()
    canon_fn = (source_filename or "").strip()[:510] or None

    summary = scan_sess.create_scan_session(
        session,
        owner_user_id=owner_user_id,
        payload=ScanSessionCreatePayload(
            session_type="high_res_review",
            scanner_profile="epson_flatbed_v600_compat",
            source_device="deterministic_bulk_upload",
            session_notes=f"high_res_review_request_id={request_id}",
        ),
    )
    sess_id = int(summary.id)

    scan_sess.start_scan_session(session, owner_user_id=owner_user_id, session_id=sess_id)

    cover_ent = persist_cover_bytes_for_inventory_copy(
        session,
        settings,
        owner_user_id=owner_user_id,
        inventory_copy_id=int(row.inventory_copy_id),
        body=body,
        mime_type=mime_i,
        sha256_hex=sha_hex,
        image_width=int(width_i),
        image_height=int(height_i),
        original_filename=canon_fn,
        source_type="upload",
    )
    cid = int(cover_ent.id or 0)

    item = ScanSessionItem(
        scan_session_id=sess_id,
        inventory_copy_id=int(row.inventory_copy_id),
        cover_image_id=cid,
        source_filename=canon_fn,
        sequence_index=0,
        ingest_status="imported",
        ingest_error=None,
        image_width=int(width_i),
        image_height=int(height_i),
        image_sha256=sha_hex.lower(),
        created_at=now,
        updated_at=now,
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    scan_sess.recompute_scan_session_counters(session, sess_id)
    scan_sess.complete_scan_session(session, owner_user_id=owner_user_id, session_id=sess_id)

    row.attach_scan_session_id = sess_id
    row.attach_scan_session_item_id = int(item.id or 0)
    row.high_res_cover_image_id = cid
    row.status = "linked"
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)

    return _hydrate_review_read(session, row)


def cancel_high_res_review_request(
    session: Session,
    *,
    owner_user_id: int,
    request_id: int,
) -> HighResReviewRequestRead:
    row = _request_owned(session, owner_user_id=owner_user_id, request_id=request_id)
    if row.status in _TERMINAL_REQ:
        raise HTTPException(status_code=400, detail="Request already resolved")

    row.status = "cancelled"
    row.completed_at = utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _hydrate_review_read(session, row)


def complete_high_res_review_request(
    session: Session,
    *,
    owner_user_id: int,
    request_id: int,
) -> HighResReviewRequestRead:
    row = _request_owned(session, owner_user_id=owner_user_id, request_id=request_id)
    if row.status in _TERMINAL_REQ:
        raise HTTPException(status_code=400, detail="Request already resolved")

    if row.high_res_cover_image_id is None:
        raise HTTPException(status_code=400, detail="Cannot complete before linking a deterministic high-resolution scan")

    allowed_precomplete = frozenset({"linked", "scanned"})
    if row.status not in allowed_precomplete:
        raise HTTPException(status_code=400, detail="Complete allowed only once a high-resolution scan linkage exists")

    row.status = "review_complete"
    row.completed_at = utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _hydrate_review_read(session, row)
