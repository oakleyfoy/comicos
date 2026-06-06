"""P78-01 sell queue and listing draft persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P78_DRAFT_STATUSES = ("CANDIDATE", "DRAFT", "READY", "ARCHIVED")
P78_QUEUE_PRIORITIES = ("HIGH", "MEDIUM", "WATCH")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P78ListingDraft(SQLModel, table=True):
    __tablename__ = "p78_listing_draft"
    __table_args__ = (
        SAIndex("ix_p78_draft_owner_status", "owner_user_id", "status", "updated_at", "id"),
        SAIndex("ix_p78_draft_owner_copy", "owner_user_id", "inventory_copy_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    status: str = Field(default="CANDIDATE", max_length=16, nullable=False, index=True)
    title: str = Field(default="", max_length=512, nullable=False)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    condition_suggested: str = Field(default="NM", max_length=32, nullable=False)
    category: str = Field(default="Comics", max_length=120, nullable=False)
    shipping_recommendation: str = Field(default="Gemini Mailer", max_length=120, nullable=False)
    suggested_sell_quantity: int = Field(default=1, nullable=False)
    fmv_at_generation: float = Field(default=0.0, nullable=False)
    quick_sale_price: float = Field(default=0.0, nullable=False)
    market_price: float = Field(default=0.0, nullable=False)
    premium_price: float = Field(default=0.0, nullable=False)
    priority: str = Field(default="MEDIUM", max_length=16, nullable=False)
    signals_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    bundle_key: str | None = Field(default=None, max_length=256, nullable=True, index=True)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
