"""P105 missing-barcode repair queue (intake-discovered UPCs not in catalog_upc)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P105_QUEUE_PENDING = "pending"
P105_QUEUE_RESOLVED = "resolved"
P105_QUEUE_CONFLICT = "conflict"


class P105MissingBarcodeQueue(SQLModel, table=True):
    __tablename__ = "p105_missing_barcode_queue"

    id: int | None = Field(default=None, primary_key=True)
    barcode: str = Field(max_length=64, index=True, nullable=False)
    publisher_guess: str | None = Field(default=None, max_length=256, nullable=True)
    issue_number_from_supplement: str | None = Field(default=None, max_length=32, nullable=True)
    intake_item_id: int | None = Field(default=None, foreign_key="intake_session_item.id", index=True)
    status: str = Field(max_length=32, default=P105_QUEUE_PENDING, index=True, nullable=False)
    chosen_catalog_issue_id: int | None = Field(default=None, index=True, nullable=True)
    created_catalog_upc_id: int | None = Field(default=None, nullable=True)
    created_learned_barcode_id: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
