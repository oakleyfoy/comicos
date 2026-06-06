"""P79-01 storage foundation dashboard."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.storage_location import P79InventoryLocationAssignment, P79StorageBox, P79StorageLocation
from app.schemas.storage_foundation import P79StorageDashboardRead
from app.services.storage_assignment_service import assignment_read
from app.services.storage_capacity import aggregate_utilization, count_unassigned_copies
from app.services.storage_location_service import list_storage_boxes, list_storage_locations


def build_storage_dashboard(session: Session, *, owner_user_id: int) -> P79StorageDashboardRead:
    locs, _ = list_storage_locations(session, owner_user_id=owner_user_id, limit=50)
    boxes, _ = list_storage_boxes(session, owner_user_id=owner_user_id, limit=50)
    util = aggregate_utilization(session, owner_user_id=owner_user_id)
    assigned = len(
        session.exec(
            select(P79InventoryLocationAssignment).where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        ).all()
    )
    unassigned = count_unassigned_copies(session, owner_user_id=owner_user_id)
    location_count = len(
        session.exec(select(P79StorageLocation).where(P79StorageLocation.owner_user_id == owner_user_id)).all()
    )
    box_count = len(session.exec(select(P79StorageBox).where(P79StorageBox.owner_user_id == owner_user_id)).all())

    recent_rows = session.exec(
        select(P79InventoryLocationAssignment)
        .where(P79InventoryLocationAssignment.owner_user_id == owner_user_id)
        .order_by(P79InventoryLocationAssignment.updated_at.desc(), P79InventoryLocationAssignment.id.desc())
        .limit(10)
    ).all()
    recent = [assignment_read(session, assignment=a) for a in recent_rows]

    return P79StorageDashboardRead(
        location_count=location_count,
        box_count=box_count,
        assigned_books=assigned,
        unassigned_books=unassigned,
        total_slot_capacity=int(util["total_slot_capacity"]),
        occupied_slots=int(util["occupied_slots"]),
        available_slots=int(util["available_slots"]),
        location_utilization_pct=float(util["location_utilization_pct"]),
        shelf_utilization_pct=float(util["shelf_utilization_pct"]),
        box_utilization_pct=float(util["box_utilization_pct"]),
        recent_assignments=recent,
        locations=locs[:12],
        boxes=boxes[:12],
    )
