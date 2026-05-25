"""P36-05 convention / show operations ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConventionEvent(SQLModel, table=True):
    __tablename__ = "convention_event"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_convention_event_owner_replay"),
        SAIndex("ix_convention_event_owner_status", "owner_user_id", "status"),
        SAIndex("ix_convention_event_owner_dates", "owner_user_id", "start_date", "end_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    name: str = Field(max_length=160, nullable=False)
    venue: str | None = Field(default=None, max_length=160, nullable=True)
    city: str | None = Field(default=None, max_length=120, nullable=True)
    state: str | None = Field(default=None, max_length=80, nullable=True)
    country: str | None = Field(default=None, max_length=80, nullable=True)
    start_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    end_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    event_type: str = Field(max_length=24, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    activated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class ConventionInventoryAssignment(SQLModel, table=True):
    __tablename__ = "convention_inventory_assignment"
    __table_args__ = (
        UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_assignment_replay"),
        SAIndex(
            "ix_convention_assignment_event_item_active",
            "convention_event_id",
            "inventory_item_id",
            "removed_at",
            "created_at",
            "id",
        ),
        SAIndex("ix_convention_assignment_event_type", "convention_event_id", "assignment_type"),
    )

    id: int | None = Field(default=None, primary_key=True)
    convention_event_id: int = Field(foreign_key="convention_event.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    assignment_type: str = Field(max_length=24, nullable=False, index=True)
    local_price_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    local_price_currency: str | None = Field(default=None, max_length=8, nullable=True)
    display_location: str | None = Field(default=None, max_length=160, nullable=True)
    priority_rank: int | None = Field(default=None, nullable=True)
    assigned_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    removed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionInventoryMovement(SQLModel, table=True):
    __tablename__ = "convention_inventory_movement"
    __table_args__ = (
        UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_movement_replay"),
        SAIndex("ix_convention_movement_event_item_created", "convention_event_id", "inventory_item_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    convention_event_id: int = Field(foreign_key="convention_event.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    movement_type: str = Field(max_length=24, nullable=False, index=True)
    from_location: str | None = Field(default=None, max_length=160, nullable=True)
    to_location: str | None = Field(default=None, max_length=160, nullable=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_by_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionPriceSnapshot(SQLModel, table=True):
    __tablename__ = "convention_price_snapshot"
    __table_args__ = (
        UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_price_snapshot_replay"),
        SAIndex("ix_convention_price_event_item_created", "convention_event_id", "inventory_item_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    convention_event_id: int = Field(foreign_key="convention_event.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    price_amount: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    currency: str = Field(max_length=8, nullable=False, index=True)
    pricing_source: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConventionSaleSession(SQLModel, table=True):
    __tablename__ = "convention_sale_session"
    __table_args__ = (
        UniqueConstraint("convention_event_id", "replay_key", name="uq_convention_sale_session_replay"),
        SAIndex("ix_convention_sale_session_event_status", "convention_event_id", "status"),
        SAIndex("ix_convention_sale_session_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    convention_event_id: int = Field(foreign_key="convention_event.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    opened_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    closed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
