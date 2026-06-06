"""P79-01 occupancy and utilization calculations."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.storage_location import (
    P79_KIND_SHELF,
    P79InventoryLocationAssignment,
    P79StorageBox,
    P79StorageLocation,
    P79StorageSlot,
)


def _pct(used: int, cap: int) -> float:
    if cap <= 0:
        return 0.0
    return round(min(100.0, used / cap * 100.0), 1)


def occupied_slots_for_box(session: Session, *, box_id: int) -> int:
    return len(
        session.exec(
            select(P79InventoryLocationAssignment)
            .join(P79StorageSlot, P79InventoryLocationAssignment.storage_slot_id == P79StorageSlot.id)
            .where(P79StorageSlot.box_id == box_id)
        ).all()
    )


def box_metrics(session: Session, *, box: P79StorageBox) -> dict[str, int | float]:
    used = occupied_slots_for_box(session, box_id=int(box.id or 0))
    cap = int(box.capacity)
    return {
        "current_occupancy": used,
        "remaining_capacity": max(0, cap - used),
        "utilization_pct": _pct(used, cap),
    }


def _descendant_shelf_ids(session: Session, *, owner_user_id: int, location_id: int) -> list[int]:
    loc = session.get(P79StorageLocation, location_id)
    if loc is None or loc.owner_user_id != owner_user_id:
        return []
    if loc.location_kind == P79_KIND_SHELF:
        return [location_id]
    children = session.exec(
        select(P79StorageLocation)
        .where(P79StorageLocation.owner_user_id == owner_user_id)
        .where(P79StorageLocation.parent_id == location_id)
    ).all()
    ids: list[int] = []
    for child in children:
        ids.extend(_descendant_shelf_ids(session, owner_user_id=owner_user_id, location_id=int(child.id or 0)))
    return ids


def location_tree_metrics(
    session: Session,
    *,
    owner_user_id: int,
    location_id: int,
) -> tuple[int, int | None, float]:
    loc = session.get(P79StorageLocation, location_id)
    if loc is None:
        return 0, None, 0.0
    shelf_ids = _descendant_shelf_ids(session, owner_user_id=owner_user_id, location_id=location_id)
    if not shelf_ids and loc.location_kind == P79_KIND_SHELF:
        shelf_ids = [location_id]
    boxes = session.exec(
        select(P79StorageBox).where(P79StorageBox.shelf_location_id.in_(shelf_ids))
    ).all() if shelf_ids else []
    used = sum(occupied_slots_for_box(session, box_id=int(b.id or 0)) for b in boxes)
    cap = sum(int(b.capacity) for b in boxes)
    if loc.capacity is not None and cap == 0:
        cap = int(loc.capacity)
    rem = max(0, cap - used) if cap else None
    return used, rem, _pct(used, cap)


def aggregate_utilization(session: Session, *, owner_user_id: int) -> dict[str, float]:
    boxes = session.exec(select(P79StorageBox).where(P79StorageBox.owner_user_id == owner_user_id)).all()
    total_cap = sum(int(b.capacity) for b in boxes)
    total_used = sum(occupied_slots_for_box(session, box_id=int(b.id or 0)) for b in boxes)
    shelves = session.exec(
        select(P79StorageLocation)
        .where(P79StorageLocation.owner_user_id == owner_user_id)
        .where(P79StorageLocation.location_kind == P79_KIND_SHELF)
    ).all()
    shelf_cap = sum(int(s.capacity or 0) for s in shelves) or total_cap
    roots = session.exec(
        select(P79StorageLocation)
        .where(P79StorageLocation.owner_user_id == owner_user_id)
        .where(P79StorageLocation.parent_id.is_(None))
    ).all()
    loc_cap = sum(int(r.capacity or 0) for r in roots) or total_cap
    return {
        "box_utilization_pct": _pct(total_used, total_cap),
        "shelf_utilization_pct": _pct(total_used, shelf_cap),
        "location_utilization_pct": _pct(total_used, loc_cap),
        "total_slot_capacity": total_cap,
        "occupied_slots": total_used,
        "available_slots": max(0, total_cap - total_used),
    }


def count_unassigned_copies(session: Session, *, owner_user_id: int) -> int:
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    assigned_ids = {
        int(a.inventory_copy_id)
        for a in session.exec(
            select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        ).all()
    }
    return sum(1 for c in copies if int(c.id or 0) not in assigned_ids)
