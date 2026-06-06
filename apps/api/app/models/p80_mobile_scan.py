"""P80-01 mobile scan platform persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P80_CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")
P80_SCAN_SOURCES = ("BARCODE", "QR_STORAGE", "MANUAL", "OCR_PENDING")


class P80MobileScan(SQLModel, table=True):
    __tablename__ = "p80_mobile_scan"
    __table_args__ = (
        SAIndex("ix_p80_mobile_scan_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_p80_mobile_scan_owner_barcode", "owner_user_id", "normalized_barcode", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scan_source: str = Field(max_length=24, nullable=False, index=True)
    raw_input: str = Field(default="", sa_column=Column(Text, nullable=False))
    normalized_barcode: str = Field(default="", max_length=128, nullable=False, index=True)
    image_reference: str | None = Field(default=None, max_length=512, nullable=True)
    confidence: str = Field(max_length=8, nullable=False, index=True)
    requires_manual_review: bool = Field(default=False, nullable=False)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    book_identity_key: str = Field(default="", max_length=512, nullable=False, index=True)
    identification_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
