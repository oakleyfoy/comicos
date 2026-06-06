"""P79-01 physical storage hierarchy and inventory placement."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, String, UniqueConstraint
from sqlmodel import Field, SQLModel

P79_SOURCE = "p79-01"

P79_KIND_LOCATION = "LOCATION"
P79_KIND_ROOM = "ROOM"
P79_KIND_RACK = "RACK"
P79_KIND_SHELF = "SHELF"

P79_KIND_ORDER = {
    P79_KIND_LOCATION: 0,
    P79_KIND_ROOM: 1,
    P79_KIND_RACK: 2,
    P79_KIND_SHELF: 3,
}

P79_CHILD_KIND = {
    P79_KIND_LOCATION: P79_KIND_ROOM,
    P79_KIND_ROOM: P79_KIND_RACK,
    P79_KIND_RACK: P79_KIND_SHELF,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P79StorageLocation(SQLModel, table=True):
    """Flexible tree node: Location → Room → Rack → Shelf (optional levels)."""

    __tablename__ = "p79_storage_location"
    __table_args__ = (
        SAIndex("ix_p79_storage_loc_owner_parent", "owner_user_id", "parent_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    parent_id: int | None = Field(default=None, foreign_key="p79_storage_location.id", nullable=True, index=True)
    location_kind: str = Field(max_length=16, nullable=False, index=True)
    name: str = Field(max_length=128, nullable=False)
    description: str = Field(default="", max_length=512, nullable=False)
    capacity: int | None = Field(default=None, nullable=True)
    is_active: bool = Field(default=True, nullable=False)
    sort_order: int = Field(default=0, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P79StorageBox(SQLModel, table=True):
    __tablename__ = "p79_storage_box"
    __table_args__ = (SAIndex("ix_p79_storage_box_shelf", "shelf_location_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    shelf_location_id: int = Field(foreign_key="p79_storage_location.id", nullable=False, index=True)
    name: str = Field(max_length=128, nullable=False)
    description: str = Field(default="", max_length=512, nullable=False)
    capacity: int = Field(default=100, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P79StorageSlot(SQLModel, table=True):
    __tablename__ = "p79_storage_slot"
    __table_args__ = (
        UniqueConstraint("box_id", "slot_number", name="uq_p79_box_slot_number"),
        SAIndex("ix_p79_storage_slot_box", "box_id", "slot_number"),
    )

    id: int | None = Field(default=None, primary_key=True)
    box_id: int = Field(foreign_key="p79_storage_box.id", nullable=False, index=True)
    slot_number: int = Field(nullable=False, index=True)
    label: str = Field(default="", max_length=64, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P79InventoryLocationAssignment(SQLModel, table=True):
    __tablename__ = "p79_inventory_location_assignment"
    __table_args__ = (
        UniqueConstraint("inventory_copy_id", name="uq_p79_inv_copy_assignment"),
        SAIndex("ix_p79_inv_assign_owner", "owner_user_id", "inventory_copy_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    storage_slot_id: int = Field(foreign_key="p79_storage_slot.id", nullable=False, index=True)
    assigned_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    assigned_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True)
