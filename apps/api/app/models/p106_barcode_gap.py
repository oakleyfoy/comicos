"""P106 barcode gap resolution queue."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P106_STATUS_UNRESOLVED = "unresolved"
P106_STATUS_AUTO_IMPORTED = "auto_imported"
P106_STATUS_AUTO_ATTACHED = "auto_attached"
P106_STATUS_CONFLICT = "conflict"
P106_STATUS_REVIEW_REQUIRED = "review_required"


class BarcodeGapResolutionQueue(SQLModel, table=True):
    __tablename__ = "barcode_gap_resolution_queue"

    id: int | None = Field(default=None, primary_key=True)
    barcode: str = Field(max_length=64, nullable=False, index=True)
    normalized_barcode: str = Field(max_length=64, nullable=False, index=True)
    status: str = Field(max_length=32, nullable=False, index=True)
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    gcd_issue_id: int | None = Field(default=None, nullable=True, index=True)
    catalog_issue_id: int | None = Field(default=None, nullable=True, index=True)
    catalog_upc_id: int | None = Field(default=None, nullable=True)
    scanner_session_id: int | None = Field(default=None, nullable=True, index=True)
    photo_import_id: int | None = Field(default=None, nullable=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    resolved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    details_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
