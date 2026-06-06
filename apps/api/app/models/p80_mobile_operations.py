"""P80-02 mobile inventory operations session persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P80_INTAKE_MODES = ("ORDER", "PURCHASE", "MANUAL")
P80_INTAKE_STATUS = ("IN_PROGRESS", "COMPLETE")


class P80MobileIntakeSession(SQLModel, table=True):
    __tablename__ = "p80_mobile_intake_session"
    __table_args__ = (SAIndex("ix_p80_intake_owner_created", "owner_user_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    intake_mode: str = Field(max_length=16, nullable=False, index=True)
    order_id: int | None = Field(default=None, foreign_key="customer_order.id", nullable=True, index=True)
    status: str = Field(max_length=16, nullable=False, index=True)
    expected_count: int = Field(default=0, nullable=False)
    scanned_count: int = Field(default=0, nullable=False)
    received_count: int = Field(default=0, nullable=False)
    duplicate_scan_count: int = Field(default=0, nullable=False)
    unknown_scan_count: int = Field(default=0, nullable=False)
    scans_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class P80MobileAuditLink(SQLModel, table=True):
    """Tracks mobile-started audits (P79 session id)."""

    __tablename__ = "p80_mobile_audit_link"
    __table_args__ = (SAIndex("ix_p80_audit_link_owner", "owner_user_id", "p79_audit_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    p79_audit_id: int = Field(nullable=False, index=True)
    scope_box_id: int | None = Field(default=None, nullable=True, index=True)
    scope_location_id: int | None = Field(default=None, nullable=True, index=True)
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
