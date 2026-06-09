from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Column, DateTime, JSON, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReceivingSession(SQLModel, table=True):
    __tablename__ = "receiving_session"

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    status: str = Field(default="ACTIVE", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    total_items: int = Field(default=0, nullable=False)
    verified_items: int = Field(default=0, nullable=False)
    review_items: int = Field(default=0, nullable=False)
    unknown_items: int = Field(default=0, nullable=False)
    confirmed_items: int = Field(default=0, nullable=False)
    skipped_items: int = Field(default=0, nullable=False)
    capture_source: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    session_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    purchase_order_id: int | None = Field(default=None, foreign_key="customer_order.id", nullable=True, index=True)
    purchase_mode: str | None = Field(default=None, max_length=20, nullable=True, index=True)
    purchase_source_type: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    purchase_label: str | None = Field(default=None, max_length=255, nullable=True)
    seller_name: str | None = Field(default=None, max_length=255, nullable=True)
    purchase_date: date | None = Field(default=None, nullable=True)
    amount_paid: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    shipping_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    tax_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    purchase_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    allocation_method: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    allocation_details_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    inventory_created_count: int = Field(default=0, nullable=False)
    live_capture_stats_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class ReceivingSessionItem(SQLModel, table=True):
    __tablename__ = "receiving_session_item"
    __table_args__ = (
        UniqueConstraint("receiving_session_id", "sequence_index", name="uq_receiving_session_item_sequence_idx"),
    )

    id: int | None = Field(default=None, primary_key=True)
    receiving_session_id: int = Field(foreign_key="receiving_session.id", nullable=False, index=True)
    sequence_index: int = Field(nullable=False, index=True)
    source_filename: str | None = Field(default=None, max_length=510, nullable=True)
    mime_type: str | None = Field(default=None, max_length=255, nullable=True)
    image_width: int | None = Field(default=None, nullable=True)
    image_height: int | None = Field(default=None, nullable=True)
    image_sha256: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    capture_source: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    frame_fingerprint: str | None = Field(default=None, max_length=64, nullable=True, index=True)
    frame_sequence_index: int | None = Field(default=None, nullable=True, index=True)
    stable_frame_count: int = Field(default=0, nullable=False)
    recognition_bucket: str = Field(default="PENDING", max_length=20, nullable=False, index=True)
    status: str = Field(default="PENDING", max_length=20, nullable=False, index=True)
    recognition_confidence: float | None = Field(default=None, nullable=True)
    recognition_latency_ms: int | None = Field(default=None, nullable=True)
    capture_started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    capture_completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    recognition_snapshot_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    candidate_snapshot_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    selected_candidate_index: int | None = Field(default=None, nullable=True)
    selected_candidate_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    duplicate_of_item_id: int | None = Field(default=None, foreign_key="receiving_session_item.id", nullable=True, index=True)
    duplicate_suppressed: bool = Field(default=False, nullable=False)
    action_taken: str | None = Field(default=None, max_length=40, nullable=True, index=True)
    action_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    capture_metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    uploaded_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    recognized_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    confirmed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    skipped_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))

