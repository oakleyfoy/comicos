from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


ACQUISITION_SOURCE_TYPES = ("COLLECTION_GAP", "WANT_LIST", "MANUAL")
ACQUISITION_OPPORTUNITY_TYPES = (
    "COLLECTION_GAP",
    "WANT_LIST_ITEM",
    "KEY_TARGET",
    "MILESTONE_TARGET",
    "RUN_COMPLETION_TARGET",
)


class AcquisitionOpportunity(SQLModel, table=True):
    __tablename__ = "acquisition_opportunity"
    __table_args__ = (
        SAIndex(
            "ix_acq_opp_owner_source",
            "owner_user_id",
            "source_type",
            "source_reference_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_acq_opp_owner_type", "owner_user_id", "opportunity_type", "id"),
        SAIndex("ix_acq_opp_owner_priority", "owner_user_id", "priority_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    source_type: str = Field(max_length=32, nullable=False)
    source_reference_id: int | None = Field(default=None, nullable=True, index=True)
    publisher: str = Field(default="", max_length=120, nullable=False)
    series_name: str = Field(max_length=200, nullable=False)
    issue_number: str = Field(max_length=32, nullable=False)
    variant_description: str | None = Field(default=None, max_length=200, nullable=True)
    opportunity_type: str = Field(max_length=32, nullable=False, index=True)
    priority_score: float = Field(nullable=False, index=True)
    confidence_score: float = Field(nullable=False)
    estimated_fmv: float | None = Field(default=None, nullable=True)
    target_price: float | None = Field(default=None, nullable=True)
    value_gap: float | None = Field(default=None, nullable=True)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
