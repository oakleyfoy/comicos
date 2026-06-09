"""P92-07 durable import line cover resolution audit rows."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class P92ImportLineCoverResolution(SQLModel, table=True):
    __tablename__ = "p92_import_line_cover_resolution"
    __table_args__ = (
        SAIndex(
            "ix_p92_import_line_cover_draft_line",
            "draft_import_id",
            "line_index",
            unique=True,
        ),
        SAIndex("ix_p92_import_line_cover_inventory", "inventory_copy_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    draft_import_id: int = Field(foreign_key="draft_import.id", nullable=False, index=True)
    line_index: int = Field(nullable=False, ge=0)
    inventory_copy_id: int | None = Field(
        default=None,
        foreign_key="inventory_copy.id",
        nullable=True,
    )
    cover_url: str | None = Field(default=None, max_length=2048)
    cover_source: str | None = Field(default=None, max_length=32)
    cover_confidence: float | None = Field(default=None)
    variant_confidence: float | None = Field(default=None)
    source_url: str | None = Field(default=None, max_length=2048)
    source_sku: str | None = Field(default=None, max_length=128)
    verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    verified_by: str | None = Field(default=None, max_length=16)
    resolution_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
