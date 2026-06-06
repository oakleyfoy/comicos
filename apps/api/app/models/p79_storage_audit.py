"""P79-02 storage audit sessions and entries."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P79_AUDIT_SOURCE = "p79-02"

AUDIT_DRAFT = "DRAFT"
AUDIT_IN_PROGRESS = "IN_PROGRESS"
AUDIT_COMPLETED = "COMPLETED"
AUDIT_CANCELLED = "CANCELLED"

ENTRY_EXPECTED = "EXPECTED"
ENTRY_VERIFIED = "VERIFIED"
ENTRY_MISSING = "MISSING"
ENTRY_UNEXPECTED = "UNEXPECTED"
ENTRY_DUPLICATE = "DUPLICATE"
ENTRY_MOVED = "MOVED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P79StorageAuditSession(SQLModel, table=True):
    __tablename__ = "p79_storage_audit_session"
    __table_args__ = (SAIndex("ix_p79_audit_session_owner", "owner_user_id", "started_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    audit_name: str = Field(max_length=160, nullable=False)
    scope_kind: str = Field(max_length=16, nullable=False, index=True)
    scope_location_id: int | None = Field(default=None, foreign_key="p79_storage_location.id", nullable=True, index=True)
    scope_box_id: int | None = Field(default=None, foreign_key="p79_storage_box.id", nullable=True, index=True)
    status: str = Field(default=AUDIT_DRAFT, max_length=16, nullable=False, index=True)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    expected_count: int = Field(default=0, nullable=False)
    verified_count: int = Field(default=0, nullable=False)
    missing_count: int = Field(default=0, nullable=False)
    unexpected_count: int = Field(default=0, nullable=False)
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P79StorageAuditEntry(SQLModel, table=True):
    __tablename__ = "p79_storage_audit_entry"
    __table_args__ = (SAIndex("ix_p79_audit_entry_session", "audit_session_id", "entry_status", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    audit_session_id: int = Field(foreign_key="p79_storage_audit_session.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    storage_box_id: int | None = Field(default=None, foreign_key="p79_storage_box.id", nullable=True, index=True)
    slot_number: int | None = Field(default=None, nullable=True)
    entry_status: str = Field(default=ENTRY_EXPECTED, max_length=16, nullable=False, index=True)
    title_snapshot: str = Field(default="", max_length=256, nullable=False)
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
