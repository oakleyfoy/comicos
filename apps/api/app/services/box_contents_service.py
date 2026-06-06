"""P79-02 box contents with sections and flags."""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models.storage_location import P79InventoryLocationAssignment, P79StorageBox, P79StorageSlot
from app.schemas.storage_locator_audit import (
    P79BoxContentRowRead,
    P79BoxContentsRead,
    P79BoxSectionGroupRead,
)
from app.services.storage_capacity import box_metrics, occupied_slots_for_box
from app.services.storage_copy_meta import copy_display_meta, section_for_slot
from app.services.storage_missing_detection import flag_for_copy_in_box


def get_box_contents(session: Session, *, owner_user_id: int, box_id: int) -> P79BoxContentsRead:
    box = session.get(P79StorageBox, box_id)
    if box is None or box.owner_user_id != owner_user_id:
        raise ValueError("Box not found")

    from app.models.asset_ledger import InventoryCopy

    slots = session.exec(
        select(P79StorageSlot)
        .where(P79StorageSlot.box_id == box_id)
        .order_by(P79StorageSlot.slot_number.asc())
    ).all()

    rows: list[P79BoxContentRowRead] = []
    total_fmv = Decimal("0")
    flagged: list[P79BoxContentRowRead] = []

    for slot in slots:
        assign = session.exec(
            select(P79InventoryLocationAssignment).where(
                P79InventoryLocationAssignment.storage_slot_id == int(slot.id or 0)
            )
        ).first()
        if assign is None:
            continue
        copy = session.get(InventoryCopy, assign.inventory_copy_id)
        if copy is None:
            continue
        meta = copy_display_meta(session, copy)
        fmv = copy.current_fmv
        if fmv is not None:
            total_fmv += fmv
        flag = flag_for_copy_in_box(session, owner_user_id=owner_user_id, copy=copy, box_id=box_id)
        row = P79BoxContentRowRead(
            inventory_copy_id=int(copy.id or 0),
            slot_number=int(slot.slot_number),
            section=section_for_slot(int(slot.slot_number)),
            series_name=meta["series_name"],
            issue_number=meta["issue_number"],
            variant_label=meta["variant_label"],
            estimated_fmv=fmv,
            flag=flag,
        )
        rows.append(row)
        if flag:
            flagged.append(row)

    sections_map: dict[str, list[P79BoxContentRowRead]] = {}
    for row in rows:
        sections_map.setdefault(row.section, []).append(row)
    sections = [
        P79BoxSectionGroupRead(section=k, items=v) for k, v in sorted(sections_map.items(), key=lambda x: x[0])
    ]

    m = box_metrics(session, box=box)
    used = occupied_slots_for_box(session, box_id=box_id)
    if used > int(box.capacity):
        flagged.append(
            P79BoxContentRowRead(
                inventory_copy_id=0,
                slot_number=0,
                section="",
                series_name="",
                issue_number="",
                variant_label="",
                flag="OVER_CAPACITY",
            )
        )

    return P79BoxContentsRead(
        box_id=box_id,
        box_name=box.name,
        capacity=int(box.capacity),
        total_count=used,
        utilization_pct=float(m["utilization_pct"]),
        total_estimated_fmv=total_fmv,
        sections=sections,
        flagged_rows=flagged,
    )
