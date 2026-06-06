"""P79-01 manual and suggested slot assignment."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.asset_ledger import ComicIssue, ComicTitle, InventoryCopy, Variant
from app.models.storage_location import (
    P79InventoryLocationAssignment,
    P79StorageBox,
    P79StorageLocation,
    P79StorageSlot,
)
from app.schemas.storage_foundation import P79StorageAssignmentRead, P79StorageLocationPathSegment
from app.services.storage_capacity import occupied_slots_for_box


class StorageAssignmentError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_copy(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> InventoryCopy:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.user_id != owner_user_id:
        raise StorageAssignmentError("Inventory copy not found")
    return copy


def _get_box(session: Session, *, owner_user_id: int, box_id: int) -> P79StorageBox:
    box = session.get(P79StorageBox, box_id)
    if box is None or box.owner_user_id != owner_user_id:
        raise StorageAssignmentError("Storage box not found")
    return box


def suggest_next_slot_number(session: Session, *, box_id: int) -> int | None:
    box = session.get(P79StorageBox, box_id)
    if box is None:
        return None
    used = occupied_slots_for_box(session, box_id=box_id)
    if used >= int(box.capacity):
        return None
    taken_rows = session.exec(
        select(P79StorageSlot.slot_number)
        .join(
            P79InventoryLocationAssignment,
            P79InventoryLocationAssignment.storage_slot_id == P79StorageSlot.id,
        )
        .where(P79StorageSlot.box_id == box_id)
    ).all()
    taken = {int(n) for n in taken_rows}
    for n in range(1, int(box.capacity) + 1):
        if n not in taken:
            return n
    return None


def _get_or_create_slot(session: Session, *, box_id: int, slot_number: int) -> P79StorageSlot:
    box = session.get(P79StorageBox, box_id)
    if box is None:
        raise StorageAssignmentError("Box not found")
    if slot_number < 1 or slot_number > int(box.capacity):
        raise StorageAssignmentError("Slot number out of box capacity range")
    slot = session.exec(
        select(P79StorageSlot).where(P79StorageSlot.box_id == box_id).where(P79StorageSlot.slot_number == slot_number)
    ).first()
    if slot is None:
        slot = P79StorageSlot(box_id=box_id, slot_number=slot_number, label=str(slot_number))
        session.add(slot)
        session.flush()
    existing = session.exec(
        select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.storage_slot_id == int(slot.id or 0))
    ).first()
    if existing is not None:
        raise StorageAssignmentError(f"Slot {slot_number} is already occupied")
    return slot


def build_location_path(
    session: Session,
    *,
    owner_user_id: int,
    shelf_location_id: int,
) -> list[P79StorageLocationPathSegment]:
    path: list[P79StorageLocationPathSegment] = []
    loc = session.get(P79StorageLocation, shelf_location_id)
    while loc is not None and loc.owner_user_id == owner_user_id:
        path.append(
            P79StorageLocationPathSegment(
                kind=loc.location_kind,
                name=loc.name,
                id=int(loc.id or 0),
            )
        )
        if loc.parent_id is None:
            break
        loc = session.get(P79StorageLocation, loc.parent_id)
    path.reverse()
    return path


def _variant_label(session: Session, variant_id: int) -> tuple[str, str, str]:
    variant = session.get(Variant, variant_id)
    if variant is None:
        return ("", "", "")
    issue = session.get(ComicIssue, variant.comic_issue_id)
    if issue is None:
        return ("", "", variant.cover_name or "")
    title = session.get(ComicTitle, issue.comic_title_id)
    series = title.name if title else ""
    parts = [variant.cover_name, variant.printing, variant.ratio]
    variant_label = " / ".join(p for p in parts if p) or "Standard"
    return (series, issue.issue_number, variant_label)


def assignment_read(
    session: Session,
    *,
    assignment: P79InventoryLocationAssignment,
    copy: InventoryCopy | None = None,
) -> P79StorageAssignmentRead:
    slot = session.get(P79StorageSlot, assignment.storage_slot_id)
    if slot is None:
        raise StorageAssignmentError("Slot missing")
    box = session.get(P79StorageBox, slot.box_id)
    if box is None:
        raise StorageAssignmentError("Box missing")
    path = build_location_path(session, owner_user_id=assignment.owner_user_id, shelf_location_id=box.shelf_location_id)
    if copy is None:
        copy = session.get(InventoryCopy, assignment.inventory_copy_id)
    series, issue, variant = ("", "", "")
    if copy is not None:
        series, issue, variant = _variant_label(session, int(copy.variant_id))
    return P79StorageAssignmentRead(
        id=int(assignment.id or 0),
        inventory_copy_id=int(assignment.inventory_copy_id),
        box_id=int(box.id or 0),
        slot_number=int(slot.slot_number),
        location_path=path,
        box_name=box.name,
        assigned_at=assignment.assigned_at,
        updated_at=assignment.updated_at,
        assigned_by_user_id=assignment.assigned_by_user_id,
        series_name=series or None,
        issue_number=issue or None,
        variant_label=variant or None,
    )


def assign_inventory_copy(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    box_id: int,
    slot_number: int | None = None,
    use_suggested_slot: bool = False,
    assigned_by_user_id: int | None = None,
) -> P79StorageAssignmentRead:
    copy = _get_copy(session, owner_user_id=owner_user_id, inventory_copy_id=inventory_copy_id)
    box = _get_box(session, owner_user_id=owner_user_id, box_id=box_id)
    if use_suggested_slot or slot_number is None:
        slot_number = suggest_next_slot_number(session, box_id=box_id)
        if slot_number is None:
            raise StorageAssignmentError("No available slots in box")
    slot = _get_or_create_slot(session, box_id=box_id, slot_number=slot_number)
    prior = session.exec(
        select(P79InventoryLocationAssignment)
        .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        .where(P79InventoryLocationAssignment.inventory_copy_id == inventory_copy_id)
    ).first()
    now = utc_now()
    if prior is not None:
        prior.storage_slot_id = int(slot.id or 0)
        prior.updated_at = now
        prior.assigned_by_user_id = assigned_by_user_id
        session.add(prior)
        session.commit()
        session.refresh(prior)
        return assignment_read(session, assignment=prior, copy=copy)
    row = P79InventoryLocationAssignment(
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
        storage_slot_id=int(slot.id or 0),
        assigned_at=now,
        updated_at=now,
        assigned_by_user_id=assigned_by_user_id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return assignment_read(session, assignment=row, copy=copy)
