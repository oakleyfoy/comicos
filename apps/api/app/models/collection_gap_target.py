from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


GAP_TARGET_STATUSES = ("ACTIVE", "ACQUIRED", "REMOVED")
GAP_TARGET_SOURCES = ("COLLECTION_GAP_BUILDER",)
GAP_TARGET_PRIORITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
DEFAULT_GAP_TARGET_PRIORITY = "MEDIUM"
DEFAULT_GAP_TARGET_STATUS = "ACTIVE"
DEFAULT_GAP_TARGET_SOURCE = "COLLECTION_GAP_BUILDER"


class CollectionGapTarget(SQLModel, table=True):
    __tablename__ = "collection_gap_target"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "volume_id",
            "normalized_issue_number",
            "catalog_issue_id",
            name="uq_collection_gap_target_user_vol_issue_catalog",
        ),
        SAIndex("ix_collection_gap_target_user_volume_issue", "user_id", "volume_id", "normalized_issue_number"),
        SAIndex("ix_collection_gap_target_user_status", "user_id", "target_status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(default="", max_length=120, nullable=False)
    series_title: str = Field(max_length=255, nullable=False)
    volume_id: int = Field(nullable=False, index=True)
    issue_number: str = Field(max_length=32, nullable=False)
    normalized_issue_number: str = Field(max_length=32, nullable=False)
    catalog_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    placeholder_issue_id: int | None = Field(
        default=None,
        foreign_key="acquisition_placeholder_issue.id",
        nullable=True,
        index=True,
    )
    target_status: str = Field(default=DEFAULT_GAP_TARGET_STATUS, max_length=16, nullable=False, index=True)
    source: str = Field(default=DEFAULT_GAP_TARGET_SOURCE, max_length=40, nullable=False)
    priority: str = Field(default=DEFAULT_GAP_TARGET_PRIORITY, max_length=16, nullable=False)
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
