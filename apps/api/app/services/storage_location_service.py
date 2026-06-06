"""P79-01 storage location CRUD and office template seed."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.storage_location import (
    P79_KIND_LOCATION,
    P79_KIND_ORDER,
    P79_KIND_RACK,
    P79_KIND_SHELF,
    P79StorageBox,
    P79StorageLocation,
)
from app.schemas.storage_foundation import P79StorageLocationRead
from app.services.storage_capacity import box_metrics, location_tree_metrics


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StorageLocationError(ValueError):
    pass


def _validate_parent_kind(parent: P79StorageLocation | None, child_kind: str) -> None:
    if child_kind not in P79_KIND_ORDER:
        raise StorageLocationError(f"Invalid location_kind: {child_kind}")
    if parent is None:
        if child_kind != P79_KIND_LOCATION:
            raise StorageLocationError("Root nodes must be LOCATION kind")
        return
    parent_order = P79_KIND_ORDER[parent.location_kind]
    child_order = P79_KIND_ORDER[child_kind]
    if child_order <= parent_order:
        raise StorageLocationError(
            f"{child_kind} cannot be nested under {parent.location_kind}"
        )


def create_storage_location(
    session: Session,
    *,
    owner_user_id: int,
    parent_id: int | None,
    location_kind: str,
    name: str,
    description: str = "",
    capacity: int | None = None,
    is_active: bool = True,
    sort_order: int = 0,
) -> P79StorageLocation:
    parent = None
    if parent_id is not None:
        parent = session.get(P79StorageLocation, parent_id)
        if parent is None or parent.owner_user_id != owner_user_id:
            raise StorageLocationError("Parent location not found")
    _validate_parent_kind(parent, location_kind.upper())
    row = P79StorageLocation(
        owner_user_id=owner_user_id,
        parent_id=parent_id,
        location_kind=location_kind.upper(),
        name=name.strip(),
        description=description.strip(),
        capacity=capacity,
        is_active=is_active,
        sort_order=sort_order,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_storage_locations(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[P79StorageLocationRead], int]:
    rows = session.exec(
        select(P79StorageLocation)
        .where(P79StorageLocation.owner_user_id == owner_user_id)
        .order_by(P79StorageLocation.sort_order, P79StorageLocation.name, P79StorageLocation.id)
    ).all()
    reads: list[P79StorageLocationRead] = []
    for loc in rows:
        occ, rem, util = location_tree_metrics(session, owner_user_id=owner_user_id, location_id=int(loc.id or 0))
        reads.append(
            P79StorageLocationRead(
                id=int(loc.id or 0),
                parent_id=loc.parent_id,
                location_kind=loc.location_kind,
                name=loc.name,
                description=loc.description,
                capacity=loc.capacity,
                is_active=loc.is_active,
                sort_order=loc.sort_order,
                created_at=loc.created_at,
                updated_at=loc.updated_at,
                utilization_pct=util,
                current_occupancy=occ,
                remaining_capacity=rem,
            )
        )
    page = reads[offset : offset + limit]
    return page, len(reads)


def create_storage_box(
    session: Session,
    *,
    owner_user_id: int,
    shelf_location_id: int,
    name: str,
    description: str = "",
    capacity: int = 100,
    is_active: bool = True,
) -> P79StorageBox:
    shelf = session.get(P79StorageLocation, shelf_location_id)
    if shelf is None or shelf.owner_user_id != owner_user_id:
        raise StorageLocationError("Shelf location not found")
    if shelf.location_kind != P79_KIND_SHELF:
        raise StorageLocationError("Box must attach to a SHELF location")
    row = P79StorageBox(
        owner_user_id=owner_user_id,
        shelf_location_id=shelf_location_id,
        name=name.strip(),
        description=description.strip(),
        capacity=capacity,
        is_active=is_active,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_storage_boxes(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list, int]:
    from app.schemas.storage_foundation import P79StorageBoxRead
    from app.services.storage_assignment_service import suggest_next_slot_number

    rows = session.exec(
        select(P79StorageBox)
        .where(P79StorageBox.owner_user_id == owner_user_id)
        .order_by(P79StorageBox.name, P79StorageBox.id)
    ).all()
    reads: list[P79StorageBoxRead] = []
    for box in rows:
        m = box_metrics(session, box=box)
        suggested = suggest_next_slot_number(session, box_id=int(box.id or 0))
        reads.append(
            P79StorageBoxRead(
                id=int(box.id or 0),
                shelf_location_id=box.shelf_location_id,
                name=box.name,
                description=box.description,
                capacity=box.capacity,
                is_active=box.is_active,
                current_occupancy=m["current_occupancy"],
                remaining_capacity=m["remaining_capacity"],
                utilization_pct=m["utilization_pct"],
                suggested_next_slot=suggested,
                created_at=box.created_at,
                updated_at=box.updated_at,
            )
        )
    page = reads[offset : offset + limit]
    return page, len(reads)


def seed_office_template(session: Session, *, owner_user_id: int) -> P79StorageLocation:
    """Optional default: Office → Rack A → Shelves 1–3 → Boxes 1–3 (capacity 100 each)."""
    existing = session.exec(
        select(P79StorageLocation)
        .where(P79StorageLocation.owner_user_id == owner_user_id)
        .where(P79StorageLocation.name == "Office")
        .where(P79StorageLocation.location_kind == P79_KIND_LOCATION)
    ).first()
    if existing is not None:
        return existing

    office = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=None,
        location_kind=P79_KIND_LOCATION,
        name="Office",
        description="Default office storage",
    )
    rack = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=int(office.id or 0),
        location_kind=P79_KIND_RACK,
        name="Rack A",
    )
    for shelf_num in (1, 2, 3):
        shelf = create_storage_location(
            session,
            owner_user_id=owner_user_id,
            parent_id=int(rack.id or 0),
            location_kind=P79_KIND_SHELF,
            name=f"Shelf {shelf_num}",
            capacity=300,
        )
        for box_num in (1, 2, 3):
            create_storage_box(
                session,
                owner_user_id=owner_user_id,
                shelf_location_id=int(shelf.id or 0),
                name=f"Box {box_num}",
                capacity=100,
            )
    session.refresh(office)
    return office
