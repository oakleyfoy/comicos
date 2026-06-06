"""Shared P79 test fixtures."""

from __future__ import annotations

from sqlmodel import Session

from app.models.storage_location import P79_KIND_LOCATION, P79_KIND_RACK, P79_KIND_ROOM, P79_KIND_SHELF
from app.services.storage_location_service import create_storage_box, create_storage_location


def build_office_rack_shelf_box(session: Session, *, owner_user_id: int) -> tuple[int, int]:
    """Office → Rack A → Shelf 3 → Box 17 (capacity 100). Returns (box_id, shelf_id)."""
    office = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=None,
        location_kind=P79_KIND_LOCATION,
        name="Office",
    )
    room = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=int(office.id or 0),
        location_kind=P79_KIND_ROOM,
        name="Main",
    )
    rack = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=int(room.id or 0),
        location_kind=P79_KIND_RACK,
        name="A",
    )
    shelf = create_storage_location(
        session,
        owner_user_id=owner_user_id,
        parent_id=int(rack.id or 0),
        location_kind=P79_KIND_SHELF,
        name="3",
        capacity=100,
    )
    box = create_storage_box(
        session,
        owner_user_id=owner_user_id,
        shelf_location_id=int(shelf.id or 0),
        name="17",
        capacity=100,
    )
    return int(box.id or 0), int(shelf.id or 0)
