"""P72-02 grading operations queue, batches, audit, and inventory grading history."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P72GradingBatch(SQLModel, table=True):
    __tablename__ = "p72_grading_batch"
    __table_args__ = (
        SAIndex("ix_p72_grading_batch_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    batch_name: str = Field(max_length=160, nullable=False)
    target_grader: str = Field(default="CGC", max_length=16, nullable=False, index=True)
    submission_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True, index=True))
    book_count: int = Field(default=0, nullable=False, ge=0)
    estimated_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    grader_received_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    estimated_completion_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    actual_completion_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    turnaround_days: int | None = Field(default=None, nullable=True)
    batch_status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P72GradingQueueEntry(SQLModel, table=True):
    __tablename__ = "p72_grading_queue_entry"
    __table_args__ = (
        SAIndex("ix_p72_grading_queue_owner_status", "owner_user_id", "status", "id"),
        SAIndex("ix_p72_grading_queue_batch", "p72_grading_batch_id", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    p72_grading_batch_id: int | None = Field(
        default=None,
        foreign_key="p72_grading_batch.id",
        nullable=True,
        index=True,
    )
    title: str = Field(max_length=256, nullable=False)
    publisher: str = Field(default="", max_length=80, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    status: str = Field(max_length=32, nullable=False, index=True)
    target_grader: str = Field(default="CGC", max_length=16, nullable=False)
    submission_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    received_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    estimated_completion_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    actual_completion_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    turnaround_days: int | None = Field(default=None, nullable=True)
    estimated_grading_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    actual_grade: str | None = Field(default=None, max_length=32, nullable=True)
    certification_number: str | None = Field(default=None, max_length=64, nullable=True)
    slab_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    final_grading_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    search_blob: str = Field(default="", max_length=512, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P72GradingAuditLog(SQLModel, table=True):
    __tablename__ = "p72_grading_audit_log"
    __table_args__ = (
        SAIndex("ix_p72_grading_audit_queue_created", "queue_entry_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    queue_entry_id: int = Field(foreign_key="p72_grading_queue_entry.id", nullable=False, index=True)
    event_type: str = Field(max_length=40, nullable=False, index=True)
    prior_status: str | None = Field(default=None, max_length=32, nullable=True)
    new_status: str | None = Field(default=None, max_length=32, nullable=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_by_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class P72InventoryGradingHistory(SQLModel, table=True):
    __tablename__ = "p72_inventory_grading_history"
    __table_args__ = (
        SAIndex("ix_p72_inv_grading_hist_copy", "inventory_copy_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    queue_entry_id: int | None = Field(default=None, foreign_key="p72_grading_queue_entry.id", nullable=True, index=True)
    actual_grade: str = Field(max_length=32, nullable=False)
    certification_number: str | None = Field(default=None, max_length=64, nullable=True)
    slab_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    final_grading_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    target_grader: str = Field(max_length=16, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
