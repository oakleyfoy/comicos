"""P79-02 inventory locator across storage and metadata."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.storage_location import (
    P79_KIND_RACK,
    P79_KIND_ROOM,
    P79_KIND_SHELF,
    P79InventoryLocationAssignment,
    P79StorageBox,
    P79StorageLocation,
    P79StorageSlot,
)
from app.schemas.storage_locator_audit import (
    P79InventoryLocatorResponse,
    P79LocatorMatchRead,
    P79LocatorPathRead,
)
from app.services.storage_assignment_service import build_location_path
from app.services.storage_copy_meta import copy_display_meta, section_for_slot


def _path_fields(session: Session, *, owner_user_id: int, box: P79StorageBox, slot_number: int) -> P79LocatorPathRead:
    segments = build_location_path(session, owner_user_id=owner_user_id, shelf_location_id=box.shelf_location_id)
    room = rack = shelf = None
    for seg in segments:
        if seg.kind == P79_KIND_ROOM:
            room = seg.name
        elif seg.kind == P79_KIND_RACK:
            rack = seg.name
        elif seg.kind == P79_KIND_SHELF:
            shelf = seg.name
    section = section_for_slot(slot_number)
    path_text = " / ".join(s.name for s in segments) + f" / {box.name} / {section} / Slot {slot_number}"
    return P79LocatorPathRead(
        room=room,
        rack=rack,
        shelf=shelf,
        box=box.name,
        section=section,
        slot=slot_number,
        location_path_text=path_text,
    )


def _duplicate_copy_ids(session: Session, *, owner_user_id: int, copy: InventoryCopy) -> list[int]:
    meta = copy_display_meta(session, copy)
    key = f"{meta['series_name']}|{meta['issue_number']}|{meta['variant_label']}".lower()
    if not meta["series_name"]:
        return []
    matches: list[int] = []
    for other in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all():
        if int(other.id or 0) == int(copy.id or 0):
            continue
        om = copy_display_meta(session, other)
        ok = f"{om['series_name']}|{om['issue_number']}|{om['variant_label']}".lower()
        if ok == key:
            assigned = session.exec(
                select(P79InventoryLocationAssignment)
                .where(P79InventoryLocationAssignment.inventory_copy_id == int(other.id or 0))
            ).first()
            if assigned is not None:
                matches.append(int(other.id or 0))
    return matches


def locate_inventory(
    session: Session,
    *,
    owner_user_id: int,
    query: str,
    limit: int = 50,
    include_unassigned: bool = True,
) -> P79InventoryLocatorResponse:
    q = query.strip()
    if not q:
        return P79InventoryLocatorResponse(query=q, items=[], total_items=0, unassigned_count=0)

    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    q_lower = q.lower()
    matched: list[InventoryCopy] = []

    if q_lower.startswith("box:") and q_lower[4:].isdigit():
        box_id = int(q_lower[4:])
        box = session.get(P79StorageBox, box_id)
        if box is not None and box.owner_user_id == owner_user_id:
            slot_rows = session.exec(select(P79StorageSlot).where(P79StorageSlot.box_id == box_id)).all()
            for slot in slot_rows:
                assign = session.exec(
                    select(P79InventoryLocationAssignment).where(
                        P79InventoryLocationAssignment.storage_slot_id == int(slot.id or 0)
                    )
                ).first()
                if assign is not None:
                    copy = session.get(InventoryCopy, assign.inventory_copy_id)
                    if copy is not None:
                        matched.append(copy)
    elif q.isdigit():
        cid = int(q)
        copy = session.get(InventoryCopy, cid)
        if copy is not None and copy.user_id == owner_user_id:
            matched.append(copy)
        box = session.get(P79StorageBox, cid)
        if box is not None and box.owner_user_id == owner_user_id:
            slot_rows = session.exec(select(P79StorageSlot).where(P79StorageSlot.box_id == cid)).all()
            for slot in slot_rows:
                assign = session.exec(
                    select(P79InventoryLocationAssignment).where(
                        P79InventoryLocationAssignment.storage_slot_id == int(slot.id or 0)
                    )
                ).first()
                if assign is not None:
                    c = session.get(InventoryCopy, assign.inventory_copy_id)
                    if c is not None:
                        matched.append(c)
    else:
        from app.services.storage_copy_meta import copy_search_blob

        for copy in copies:
            blob = copy_search_blob(session, copy)
            if q_lower in blob:
                matched.append(copy)

    items: list[P79LocatorMatchRead] = []
    unassigned = 0
    seen: set[int] = set()
    for copy in matched:
        cid = int(copy.id or 0)
        if cid in seen:
            continue
        seen.add(cid)
        meta = copy_display_meta(session, copy)
        assign = session.exec(
            select(P79InventoryLocationAssignment)
            .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
            .where(P79InventoryLocationAssignment.inventory_copy_id == cid)
        ).first()
        if assign is None:
            if include_unassigned:
                unassigned += 1
                dups = _duplicate_copy_ids(session, owner_user_id=owner_user_id, copy=copy)
                items.append(
                    P79LocatorMatchRead(
                        inventory_copy_id=cid,
                        title=meta["title"],
                        series_name=meta["series_name"],
                        issue_number=meta["issue_number"],
                        variant_label=meta["variant_label"],
                        publisher=meta["publisher"],
                        assignment_status="UNASSIGNED",
                        path=P79LocatorPathRead(location_path_text="Not assigned"),
                        assigned_at=None,
                        assignment_confidence="LOW",
                        is_duplicate_assignment=len(dups) > 0,
                        duplicate_matches=dups,
                        box_id=None,
                    )
                )
            continue
        slot = session.get(P79StorageSlot, assign.storage_slot_id)
        box = session.get(P79StorageBox, slot.box_id) if slot else None
        if slot is None or box is None:
            continue
        dups = _duplicate_copy_ids(session, owner_user_id=owner_user_id, copy=copy)
        confidence = "HIGH" if not dups else "MEDIUM"
        items.append(
            P79LocatorMatchRead(
                inventory_copy_id=cid,
                title=meta["title"],
                series_name=meta["series_name"],
                issue_number=meta["issue_number"],
                variant_label=meta["variant_label"],
                publisher=meta["publisher"],
                assignment_status="ASSIGNED",
                path=_path_fields(session, owner_user_id=owner_user_id, box=box, slot_number=int(slot.slot_number)),
                assigned_at=assign.assigned_at,
                assignment_confidence=confidence,
                is_duplicate_assignment=len(dups) > 0,
                duplicate_matches=dups,
                box_id=int(box.id or 0),
            )
        )

    page = items[:limit]
    return P79InventoryLocatorResponse(
        query=q,
        items=page,
        total_items=len(items),
        unassigned_count=unassigned,
    )
