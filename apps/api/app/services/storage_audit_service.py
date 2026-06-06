"""P79-02 storage audit sessions and verification workflow."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.p79_storage_audit import (
    AUDIT_CANCELLED,
    AUDIT_COMPLETED,
    AUDIT_DRAFT,
    AUDIT_IN_PROGRESS,
    ENTRY_EXPECTED,
    ENTRY_MISSING,
    ENTRY_MOVED,
    ENTRY_UNEXPECTED,
    ENTRY_VERIFIED,
    P79StorageAuditEntry,
    P79StorageAuditSession,
)
from app.models.asset_ledger import InventoryCopy
from app.models.storage_location import P79InventoryLocationAssignment, P79StorageBox, P79StorageSlot
from app.schemas.storage_locator_audit import (
    P79StorageAuditDetailRead,
    P79StorageAuditEntryRead,
    P79StorageAuditRead,
)
from app.services.storage_assignment_service import assign_inventory_copy
from app.services.storage_copy_meta import copy_display_meta
from app.services.storage_missing_detection import build_detection_summary


class StorageAuditError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _session_read(row: P79StorageAuditSession) -> P79StorageAuditRead:
    return P79StorageAuditRead(
        id=int(row.id or 0),
        audit_name=row.audit_name,
        scope_kind=row.scope_kind,
        scope_location_id=row.scope_location_id,
        scope_box_id=row.scope_box_id,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        expected_count=row.expected_count,
        verified_count=row.verified_count,
        missing_count=row.missing_count,
        unexpected_count=row.unexpected_count,
    )


def _recount(session: Session, audit: P79StorageAuditSession) -> None:
    entries = session.exec(
        select(P79StorageAuditEntry).where(P79StorageAuditEntry.audit_session_id == int(audit.id or 0))
    ).all()
    audit.expected_count = sum(
        1 for e in entries if e.entry_status in (ENTRY_EXPECTED, ENTRY_VERIFIED, ENTRY_MISSING)
    )
    audit.verified_count = sum(1 for e in entries if e.entry_status == ENTRY_VERIFIED)
    audit.missing_count = sum(1 for e in entries if e.entry_status == ENTRY_MISSING)
    audit.unexpected_count = sum(
        1 for e in entries if e.entry_status in (ENTRY_UNEXPECTED, ENTRY_MOVED)
    )
    audit.updated_at = utc_now()
    session.add(audit)


def _assignments_for_scope(
    session: Session,
    *,
    owner_user_id: int,
    scope_box_id: int | None,
    scope_location_id: int | None,
) -> list[tuple[P79InventoryLocationAssignment, P79StorageSlot, P79StorageBox]]:
    from app.services.storage_capacity import _descendant_shelf_ids

    boxes: list[P79StorageBox] = []
    if scope_box_id is not None:
        box = session.get(P79StorageBox, scope_box_id)
        if box is None or box.owner_user_id != owner_user_id:
            raise StorageAuditError("Scope box not found")
        boxes = [box]
    elif scope_location_id is not None:
        shelf_ids = _descendant_shelf_ids(session, owner_user_id=owner_user_id, location_id=scope_location_id)
        if shelf_ids:
            boxes = list(
                session.exec(select(P79StorageBox).where(P79StorageBox.shelf_location_id.in_(shelf_ids))).all()
            )
    else:
        raise StorageAuditError("Audit scope requires box_id or location_id")

    out: list[tuple[P79InventoryLocationAssignment, P79StorageSlot, P79StorageBox]] = []
    for box in boxes:
        slots = session.exec(select(P79StorageSlot).where(P79StorageSlot.box_id == int(box.id or 0))).all()
        for slot in slots:
            assign = session.exec(
                select(P79InventoryLocationAssignment).where(
                    P79InventoryLocationAssignment.storage_slot_id == int(slot.id or 0)
                )
            ).first()
            if assign is not None:
                out.append((assign, slot, box))
    return out


def create_audit_session(
    session: Session,
    *,
    owner_user_id: int,
    audit_name: str,
    scope_box_id: int | None = None,
    scope_location_id: int | None = None,
) -> P79StorageAuditSession:
    scope_kind = "BOX" if scope_box_id is not None else "LOCATION"
    row = P79StorageAuditSession(
        owner_user_id=owner_user_id,
        audit_name=audit_name.strip(),
        scope_kind=scope_kind,
        scope_location_id=scope_location_id,
        scope_box_id=scope_box_id,
        status=AUDIT_IN_PROGRESS,
        started_at=utc_now(),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(row)
    session.flush()
    pairs = _assignments_for_scope(
        session,
        owner_user_id=owner_user_id,
        scope_box_id=scope_box_id,
        scope_location_id=scope_location_id,
    )
    for assign, slot, box in pairs:
        copy = session.get(InventoryCopy, assign.inventory_copy_id)
        meta = copy_display_meta(session, copy) if copy else {"title": f"Copy {assign.inventory_copy_id}"}
        session.add(
            P79StorageAuditEntry(
                audit_session_id=int(row.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=int(assign.inventory_copy_id),
                storage_box_id=int(box.id or 0),
                slot_number=int(slot.slot_number),
                entry_status=ENTRY_EXPECTED,
                title_snapshot=meta.get("title", ""),
            )
        )
    session.commit()
    session.refresh(row)
    _recount(session, row)
    session.commit()
    session.refresh(row)
    return row


def list_audit_sessions(session: Session, *, owner_user_id: int) -> list[P79StorageAuditRead]:
    rows = session.exec(
        select(P79StorageAuditSession)
        .where(P79StorageAuditSession.owner_user_id == owner_user_id)
        .order_by(P79StorageAuditSession.created_at.desc(), P79StorageAuditSession.id.desc())
    ).all()
    return [_session_read(r) for r in rows]


def get_audit_detail(session: Session, *, owner_user_id: int, audit_id: int) -> P79StorageAuditDetailRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise StorageAuditError("Audit not found")
    entries = session.exec(
        select(P79StorageAuditEntry)
        .where(P79StorageAuditEntry.audit_session_id == audit_id)
        .order_by(P79StorageAuditEntry.slot_number, P79StorageAuditEntry.id)
    ).all()
    det = build_detection_summary(session, owner_user_id=owner_user_id)
    return P79StorageAuditDetailRead(
        session=_session_read(audit),
        entries=[P79StorageAuditEntryRead.model_validate(e) for e in entries],
        detection_summary={
            "unassigned_books": det.unassigned_books,
            "duplicate_assignments": det.duplicate_assignments,
            "over_capacity_boxes": det.over_capacity_boxes,
            "misplaced_candidates": det.misplaced_candidates,
        },
    )


def _get_entry(session: Session, *, owner_user_id: int, audit_id: int, entry_id: int) -> P79StorageAuditEntry:
    entry = session.get(P79StorageAuditEntry, entry_id)
    if entry is None or entry.owner_user_id != owner_user_id or entry.audit_session_id != audit_id:
        raise StorageAuditError("Audit entry not found")
    return entry


def mark_verified(session: Session, *, owner_user_id: int, audit_id: int, entry_id: int) -> P79StorageAuditDetailRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise StorageAuditError("Audit not found")
    if audit.status == AUDIT_COMPLETED:
        raise StorageAuditError("Audit already completed")
    entry = _get_entry(session, owner_user_id=owner_user_id, audit_id=audit_id, entry_id=entry_id)
    entry.entry_status = ENTRY_VERIFIED
    entry.updated_at = utc_now()
    session.add(entry)
    _recount(session, audit)
    session.commit()
    return get_audit_detail(session, owner_user_id=owner_user_id, audit_id=audit_id)


def mark_missing(session: Session, *, owner_user_id: int, audit_id: int, entry_id: int, notes: str = "") -> P79StorageAuditDetailRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise StorageAuditError("Audit not found")
    entry = _get_entry(session, owner_user_id=owner_user_id, audit_id=audit_id, entry_id=entry_id)
    entry.entry_status = ENTRY_MISSING
    entry.notes = notes
    entry.updated_at = utc_now()
    session.add(entry)
    _recount(session, audit)
    session.commit()
    return get_audit_detail(session, owner_user_id=owner_user_id, audit_id=audit_id)


def record_unexpected(
    session: Session,
    *,
    owner_user_id: int,
    audit_id: int,
    inventory_copy_id: int,
    storage_box_id: int,
    slot_number: int | None = None,
    notes: str = "",
    move_to_box: bool = False,
) -> P79StorageAuditDetailRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise StorageAuditError("Audit not found")
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise StorageAuditError("Inventory copy not found")
    meta = copy_display_meta(session, copy)
    if move_to_box:
        assign_inventory_copy(
            session,
            owner_user_id=owner_user_id,
            inventory_copy_id=inventory_copy_id,
            box_id=storage_box_id,
            slot_number=slot_number,
            use_suggested_slot=slot_number is None,
            assigned_by_user_id=owner_user_id,
        )
        status = ENTRY_MOVED
    else:
        status = ENTRY_UNEXPECTED
    session.add(
        P79StorageAuditEntry(
            audit_session_id=audit_id,
            owner_user_id=owner_user_id,
            inventory_copy_id=inventory_copy_id,
            storage_box_id=storage_box_id,
            slot_number=slot_number,
            entry_status=status,
            title_snapshot=meta["title"],
            notes=notes,
        )
    )
    _recount(session, audit)
    session.commit()
    return get_audit_detail(session, owner_user_id=owner_user_id, audit_id=audit_id)


def complete_audit(session: Session, *, owner_user_id: int, audit_id: int) -> P79StorageAuditDetailRead:
    audit = session.get(P79StorageAuditSession, audit_id)
    if audit is None or audit.owner_user_id != owner_user_id:
        raise StorageAuditError("Audit not found")
    audit.status = AUDIT_COMPLETED
    audit.completed_at = utc_now()
    audit.updated_at = utc_now()
    _recount(session, audit)
    session.commit()
    return get_audit_detail(session, owner_user_id=owner_user_id, audit_id=audit_id)
