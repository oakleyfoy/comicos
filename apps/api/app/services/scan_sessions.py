"""Bulk scan-session orchestration persistence (deterministic reads/writes — no OCR / driver integration)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import CoverImage, InventoryCopy, ScanSession, ScanSessionItem
from app.models.asset_ledger import utc_now
from app.schemas.scan_sessions import (
    InventoryScanSessionOriginRead,
    ScanSessionCreatePayload,
    ScanSessionDetailRead,
    ScanSessionItemRead,
    ScanSessionItemsAppendPayload,
    ScanSessionItemUpdatePayload,
    ScanSessionItemsListRead,
    ScanSessionStatisticsRead,
    ScanSessionSummaryRead,
)


PROCESSED_STATUSES = frozenset({"imported", "queued_for_ocr", "ocr_complete", "review_required"})
OCR_COMPLETED = frozenset({"ocr_complete"})
OCR_PENDING = frozenset({"pending", "imported", "queued_for_ocr"})
REVIEW_REQUIRED = frozenset({"review_required"})
FAILURES = frozenset({"failed"})
SKIPPED = frozenset({"skipped"})
ALLOWED_INGEST_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"imported", "queued_for_ocr", "failed", "skipped"}),
    "imported": frozenset({"queued_for_ocr", "failed", "skipped"}),
    "queued_for_ocr": frozenset({"ocr_complete", "review_required", "failed", "skipped"}),
    "ocr_complete": frozenset({"review_required"}),
    "review_required": frozenset(),
    "failed": frozenset(),
    "skipped": frozenset(),
}
Terminal_SESSION = frozenset({"completed", "completed_with_errors", "cancelled"})


def _touch(row: ScanSession | ScanSessionItem) -> None:
    row.updated_at = utc_now()


def _sorted_items(items: Iterable[ScanSessionItem]) -> list[ScanSessionItem]:
    material = list(items)
    material.sort(key=lambda r: (r.sequence_index, r.id or 0))
    return material


def statistics_from_items(items: Sequence[ScanSessionItem]) -> ScanSessionStatisticsRead:
    rows = list(items)
    total = len(rows)

    def _cnt(statuses: frozenset[str]) -> int:
        return sum(1 for r in rows if r.ingest_status in statuses)

    dims = [(r.image_width, r.image_height) for r in rows if r.image_width and r.image_height]
    avg_w = sum(w for w, _ in dims) / len(dims) if dims else None
    avg_h = sum(h for _, h in dims) / len(dims) if dims else None

    fnames = [r.source_filename for r in rows if r.source_filename]
    fn_ctr = Counter(fnames)
    dup_fn_groups = sum(1 for _k, ct in fn_ctr.items() if ct > 1)
    dup_fn_excess = sum(ct - 1 for _k, ct in fn_ctr.items() if ct > 1)

    hashes = [r.image_sha256 for r in rows if r.image_sha256]
    h_ctr = Counter(hashes)
    dup_h_groups = sum(1 for _k, ct in h_ctr.items() if ct > 1)
    dup_h_excess = sum(ct - 1 for _k, ct in h_ctr.items() if ct > 1)

    return ScanSessionStatisticsRead(
        total_scans=total,
        ocr_completed=_cnt(OCR_COMPLETED),
        ocr_pending=_cnt(OCR_PENDING),
        review_required=_cnt(REVIEW_REQUIRED),
        failures=_cnt(FAILURES),
        skipped=_cnt(SKIPPED),
        average_image_width=float(avg_w) if avg_w is not None else None,
        average_image_height=float(avg_h) if avg_h is not None else None,
        duplicate_filename_groups=dup_fn_groups,
        duplicate_filename_excess_rows=dup_fn_excess,
        duplicate_image_hash_groups=dup_h_groups,
        duplicate_image_hash_excess_rows=dup_h_excess,
    )


def recompute_scan_session_counters(session: Session, scan_session_id: int) -> None:
    sess = session.get(ScanSession, scan_session_id)
    if sess is None:
        return
    stmt = select(ScanSessionItem).where(ScanSessionItem.scan_session_id == scan_session_id)
    rows = _sorted_items(session.exec(stmt).all())
    total = len(rows)
    processed = sum(1 for r in rows if r.ingest_status in PROCESSED_STATUSES)
    failed = sum(1 for r in rows if r.ingest_status in FAILURES)
    skipped = sum(1 for r in rows if r.ingest_status in SKIPPED)

    sess.total_items = total
    sess.processed_items = processed
    sess.failed_items = failed
    sess.skipped_items = skipped
    _touch(sess)
    session.add(sess)


def _assert_scan_session_owned(session: Session, *, owner_user_id: int | None, session_id: int) -> ScanSession:
    sess = session.get(ScanSession, session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Scan session not found")
    if owner_user_id is not None and sess.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan session not found")
    return sess


def _assert_inventory_owned(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> None:
    inv = session.get(InventoryCopy, inventory_copy_id)
    if inv is None or inv.user_id != owner_user_id:
        raise HTTPException(status_code=400, detail="Inventory copy out of scope for this owner")


def _assert_cover_owned(session: Session, *, owner_user_id: int, cover_image_id: int) -> CoverImage:
    row = session.get(CoverImage, cover_image_id)
    if row is None or row.inventory_copy_id is None:
        raise HTTPException(status_code=400, detail="Cover image missing or unattached inventory context")
    _assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=int(row.inventory_copy_id))
    return row


def create_scan_session(session: Session, *, owner_user_id: int, payload: ScanSessionCreatePayload) -> ScanSessionSummaryRead:
    now = utc_now()
    sess = ScanSession(
        owner_user_id=owner_user_id,
        session_type=payload.session_type,
        status="pending",
        scanner_profile=payload.scanner_profile,
        source_device=payload.source_device,
        session_notes=payload.session_notes,
        started_at=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
        total_items=0,
        processed_items=0,
        failed_items=0,
        skipped_items=0,
    )
    session.add(sess)
    session.commit()
    session.refresh(sess)
    return ScanSessionSummaryRead.model_validate(sess, from_attributes=True)


def append_scan_session_items(
    session: Session,
    *,
    owner_user_id: int,
    session_id: int,
    payload: ScanSessionItemsAppendPayload,
) -> ScanSessionDetailRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    if sess.status in Terminal_SESSION:
        raise HTTPException(status_code=400, detail="Cannot append items to a terminated scan session")

    max_idx_row = session.exec(
        select(func.max(ScanSessionItem.sequence_index)).where(ScanSessionItem.scan_session_id == session_id)
    ).first()
    next_idx = int(max_idx_row or -1) + 1

    for offset, blob in enumerate(payload.items):
        if blob.inventory_copy_id is not None:
            _assert_inventory_owned(session, owner_user_id=owner_user_id, inventory_copy_id=int(blob.inventory_copy_id))
        if blob.cover_image_id is not None:
            _assert_cover_owned(session, owner_user_id=owner_user_id, cover_image_id=int(blob.cover_image_id))
        row = ScanSessionItem(
            scan_session_id=session_id,
            inventory_copy_id=blob.inventory_copy_id,
            cover_image_id=blob.cover_image_id,
            source_filename=blob.source_filename,
            sequence_index=next_idx + offset,
            ingest_status="pending",
            ingest_error=None,
            image_width=blob.image_width,
            image_height=blob.image_height,
            image_sha256=blob.image_sha256,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(row)

    recompute_scan_session_counters(session, session_id)
    _touch(sess)
    session.add(sess)
    session.commit()
    return get_scan_session_detail(session, owner_user_id=owner_user_id, session_id=session_id)


def list_scan_sessions(
    session: Session,
    *,
    owner_user_id: int | None,
    status: str | None,
    session_type: str | None,
    limit: int,
    offset: int,
) -> list[ScanSessionSummaryRead]:
    stmt = select(ScanSession)
    if owner_user_id is not None:
        stmt = stmt.where(ScanSession.owner_user_id == owner_user_id)
    if status is not None:
        stmt = stmt.where(ScanSession.status == status)
    if session_type is not None:
        stmt = stmt.where(ScanSession.session_type == session_type)
    stmt = stmt.order_by(ScanSession.updated_at.desc(), ScanSession.id.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return [ScanSessionSummaryRead.model_validate(r, from_attributes=True) for r in rows]


def get_scan_session_detail(session: Session, *, owner_user_id: int | None, session_id: int) -> ScanSessionDetailRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    stmt = select(ScanSessionItem).where(ScanSessionItem.scan_session_id == session_id)
    rows = _sorted_items(session.exec(stmt).all())
    stats = statistics_from_items(rows)
    payload = sess.model_dump()
    payload["statistics"] = stats
    payload["items"] = [ScanSessionItemRead.model_validate(r, from_attributes=True) for r in rows]
    return ScanSessionDetailRead.model_validate(payload)


def list_scan_session_items_read(
    session: Session,
    *,
    owner_user_id: int | None,
    session_id: int,
    limit: int,
    offset: int,
) -> ScanSessionItemsListRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    all_rows = _sorted_items(
        session.exec(select(ScanSessionItem).where(ScanSessionItem.scan_session_id == session_id)).all()
    )
    stats_all = statistics_from_items(all_rows)
    page_rows = all_rows[offset : offset + limit]
    return ScanSessionItemsListRead(
        scan_session_id=session_id,
        owner_user_id=int(sess.owner_user_id),
        session_status=sess.status,
        session_type=sess.session_type,
        statistics=stats_all,
        items=[ScanSessionItemRead.model_validate(r, from_attributes=True) for r in page_rows],
    )


def owner_scan_session_dashboard(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[ScanSessionSummaryRead], list[ScanSessionSummaryRead]]:
    stmt_active = (
        select(ScanSession)
        .where(
            ScanSession.owner_user_id == owner_user_id,
            ScanSession.status.in_(("pending", "active", "paused")),
        )
        .order_by(ScanSession.updated_at.desc(), ScanSession.id.desc())
        .limit(15)
    )
    rows_active = session.exec(stmt_active).all()
    active_trim = [ScanSessionSummaryRead.model_validate(r, from_attributes=True) for r in rows_active]

    stmt_recent = (
        select(ScanSession)
        .where(
            ScanSession.owner_user_id == owner_user_id,
            ScanSession.status.in_(("completed", "completed_with_errors", "cancelled")),
        )
        .order_by(ScanSession.updated_at.desc(), ScanSession.id.desc())
        .limit(15)
    )
    rows_recent = session.exec(stmt_recent).all()
    recent_trim = [ScanSessionSummaryRead.model_validate(r, from_attributes=True) for r in rows_recent]
    return active_trim, recent_trim


def _transition_session(sess: ScanSession, new_status: str) -> None:
    cur = sess.status
    allowed: dict[str, frozenset[str]] = {
        "pending": frozenset({"active", "cancelled"}),
        "active": frozenset({"paused", "completed", "completed_with_errors", "cancelled"}),
        "paused": frozenset({"active", "completed", "completed_with_errors", "cancelled"}),
        "completed": frozenset(),
        "completed_with_errors": frozenset(),
        "cancelled": frozenset(),
    }
    nxt = allowed.get(cur, frozenset())
    if new_status not in nxt:
        raise HTTPException(status_code=400, detail=f"Cannot transition session from {cur} to {new_status}")
    sess.status = new_status
    now = utc_now()
    if new_status == "active":
        if sess.started_at is None:
            sess.started_at = now
    if new_status in ("completed", "completed_with_errors", "cancelled"):
        if sess.completed_at is None:
            sess.completed_at = now
    _touch(sess)


def start_scan_session(session: Session, *, owner_user_id: int, session_id: int) -> ScanSessionSummaryRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    if sess.status == "paused":
        _transition_session(sess, "active")
    elif sess.status == "pending":
        _transition_session(sess, "active")
    else:
        raise HTTPException(status_code=400, detail=f"Cannot start scan session while status={sess.status}")
    recompute_scan_session_counters(session, session_id)
    session.add(sess)
    session.commit()
    session.refresh(sess)
    return ScanSessionSummaryRead.model_validate(sess, from_attributes=True)


def pause_scan_session(session: Session, *, owner_user_id: int, session_id: int) -> ScanSessionSummaryRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    _transition_session(sess, "paused")
    session.add(sess)
    session.commit()
    session.refresh(sess)
    return ScanSessionSummaryRead.model_validate(sess, from_attributes=True)


def cancel_scan_session(session: Session, *, owner_user_id: int, session_id: int) -> ScanSessionSummaryRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    # cancel allowed from pending, active, paused
    if sess.status not in ("pending", "active", "paused"):
        raise HTTPException(status_code=400, detail="Session already terminal")
    _transition_session(sess, "cancelled")
    session.add(sess)
    session.commit()
    session.refresh(sess)
    return ScanSessionSummaryRead.model_validate(sess, from_attributes=True)


def complete_scan_session(session: Session, *, owner_user_id: int, session_id: int) -> ScanSessionSummaryRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    if sess.status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="Complete allowed only while active or paused")
    recompute_scan_session_counters(session, session_id)
    session.refresh(sess)
    terminal = "completed_with_errors" if sess.failed_items > 0 else "completed"
    _transition_session(sess, terminal)
    session.add(sess)
    session.commit()
    session.refresh(sess)
    return ScanSessionSummaryRead.model_validate(sess, from_attributes=True)


def patch_scan_session_item(
    session: Session,
    *,
    owner_user_id: int,
    session_id: int,
    item_id: int,
    payload: ScanSessionItemUpdatePayload,
) -> ScanSessionDetailRead:
    sess = _assert_scan_session_owned(session, owner_user_id=owner_user_id, session_id=session_id)
    item = session.get(ScanSessionItem, item_id)
    if item is None or item.scan_session_id != session_id:
        raise HTTPException(status_code=404, detail="Scan session item not found")

    prev = item.ingest_status
    nxt = payload.ingest_status
    allowed_next = ALLOWED_INGEST_TRANSITIONS.get(prev)
    if allowed_next is None or nxt not in allowed_next:
        raise HTTPException(status_code=400, detail=f"Invalid ingest transition {prev} -> {nxt}")

    item.ingest_status = nxt
    if payload.ingest_error is not None:
        item.ingest_error = payload.ingest_error
    if payload.image_width is not None:
        item.image_width = payload.image_width
    if payload.image_height is not None:
        item.image_height = payload.image_height
    if payload.image_sha256 is not None:
        item.image_sha256 = payload.image_sha256
    _touch(item)
    session.add(item)

    recompute_scan_session_counters(session, session_id)
    _touch(sess)
    session.add(sess)
    session.commit()
    return get_scan_session_detail(session, owner_user_id=owner_user_id, session_id=session_id)


def originating_scan_session_for_inventory_copy(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> InventoryScanSessionOriginRead | None:
    cov_ids_subq = select(CoverImage.id).where(CoverImage.inventory_copy_id == inventory_copy_id)

    stmt = (
        select(ScanSessionItem, ScanSession)
        .join(ScanSession, ScanSessionItem.scan_session_id == ScanSession.id)
        .where(
            ScanSession.owner_user_id == owner_user_id,
            or_(
                ScanSessionItem.inventory_copy_id == inventory_copy_id,
                ScanSessionItem.cover_image_id.in_(cov_ids_subq),
            ),
        )
    )
    pairs = session.exec(stmt).all()
    if not pairs:
        return None

    pairs.sort(key=lambda pair: (pair[1].created_at, pair[1].id, pair[0].sequence_index, pair[0].id))
    chosen_item, chosen_sess = pairs[0]

    return InventoryScanSessionOriginRead(
        scan_session_id=int(chosen_sess.id),
        session_type=str(chosen_sess.session_type),
        status=str(chosen_sess.status),
        scan_session_item_id=int(chosen_item.id),
        sequence_index=int(chosen_item.sequence_index),
        ingest_status=str(chosen_item.ingest_status),
        created_at=chosen_item.created_at,
    )

