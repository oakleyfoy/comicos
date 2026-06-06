"""P79-02 missing, misplaced, duplicate, and capacity detection."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.storage_location import (
    P79InventoryLocationAssignment,
    P79StorageBox,
    P79StorageSlot,
)
from app.schemas.storage_locator_audit import P79StorageDetectionSummaryRead
from app.services.storage_capacity import count_unassigned_copies, occupied_slots_for_box
from app.services.storage_copy_meta import copy_display_meta


def flag_for_copy_in_box(
    session: Session,
    *,
    owner_user_id: int,
    copy: InventoryCopy,
    box_id: int,
) -> str | None:
    assign = session.exec(
        select(P79InventoryLocationAssignment)
        .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        .where(P79InventoryLocationAssignment.inventory_copy_id == int(copy.id or 0))
    ).first()
    if assign is None:
        return "UNASSIGNED"
    slot = session.get(P79StorageSlot, assign.storage_slot_id)
    if slot is None or int(slot.box_id) != box_id:
        return "MISPLACED"
    meta = copy_display_meta(session, copy)
    key = f"{meta['series_name']}|{meta['issue_number']}|{meta['variant_label']}".lower()
    if not meta["series_name"]:
        return None
    for other in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all():
        if int(other.id or 0) == int(copy.id or 0):
            continue
        om = copy_display_meta(session, other)
        if f"{om['series_name']}|{om['issue_number']}|{om['variant_label']}".lower() != key:
            continue
        oa = session.exec(
            select(P79InventoryLocationAssignment).where(
                P79InventoryLocationAssignment.inventory_copy_id == int(other.id or 0)
            )
        ).first()
        if oa is not None:
            return "DUPLICATE_CANDIDATE"
    return None


def build_detection_summary(session: Session, *, owner_user_id: int) -> P79StorageDetectionSummaryRead:
    unassigned = count_unassigned_copies(session, owner_user_id=owner_user_id)
    boxes = session.exec(select(P79StorageBox).where(P79StorageBox.owner_user_id == owner_user_id)).all()
    over_cap = sum(1 for b in boxes if occupied_slots_for_box(session, box_id=int(b.id or 0)) > int(b.capacity))

    duplicate = 0
    misplaced = 0
    items: list[dict] = []
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    keys_seen: dict[str, int] = {}
    for copy in copies:
        meta = copy_display_meta(session, copy)
        key = f"{meta['series_name']}|{meta['issue_number']}|{meta['variant_label']}".lower()
        if meta["series_name"]:
            keys_seen[key] = keys_seen.get(key, 0) + 1
        assign = session.exec(
            select(P79InventoryLocationAssignment)
            .where(P79InventoryLocationAssignment.inventory_copy_id == int(copy.id or 0))
        ).first()
        if assign is None:
            continue
        slot = session.get(P79StorageSlot, assign.storage_slot_id)
        if slot is None:
            continue
        flag = flag_for_copy_in_box(
            session, owner_user_id=owner_user_id, copy=copy, box_id=int(slot.box_id)
        )
        if flag == "DUPLICATE_CANDIDATE":
            duplicate += 1
            items.append({"inventory_copy_id": int(copy.id or 0), "flag": flag})
        elif flag == "MISPLACED":
            misplaced += 1
            items.append({"inventory_copy_id": int(copy.id or 0), "flag": flag})

    dup_keys = sum(1 for v in keys_seen.values() if v > 1)

    return P79StorageDetectionSummaryRead(
        unassigned_books=unassigned,
        duplicate_assignments=max(duplicate, dup_keys),
        over_capacity_boxes=over_cap,
        misplaced_candidates=misplaced,
        items=items[:50],
    )
