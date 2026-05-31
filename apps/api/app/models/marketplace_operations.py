from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, Index as SAIndex, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_recommendation_uuid() -> str:
    return str(uuid4())


class MarketplaceRecommendation(SQLModel, table=True):
    __tablename__ = "marketplace_recommendation"
    __table_args__ = (
        UniqueConstraint("recommendation_uuid", name="uq_marketplace_recommendation_uuid"),
        SAIndex("ix_marketplace_recommendation_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_uuid: str = Field(default_factory=generate_recommendation_uuid, max_length=64, nullable=False)
    agent_execution_id: int | None = Field(default=None, foreign_key="agent_execution.id", nullable=True, index=True)
    recommendation_type: str = Field(max_length=80, nullable=False, index=True)
    title: str = Field(max_length=500, nullable=False)
    description: str = Field(max_length=2000, nullable=False)
    confidence_score: float = Field(sa_column=Column(Float, nullable=False))
    priority_score: float = Field(sa_column=Column(Float, nullable=False))
    recommendation_status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    listing_id: int | None = Field(default=None, foreign_key="marketplace_listing.id", nullable=True, index=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    marketplace_id: int | None = Field(default=None, foreign_key="marketplace_definition.id", nullable=True, index=True)
    marketplace_account_id: int | None = Field(
        default=None,
        foreign_key="marketplace_account.id",
        nullable=True,
        index=True,
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceRecommendationEvidence(SQLModel, table=True):
    __tablename__ = "marketplace_recommendation_evidence"
    __table_args__ = (SAIndex("ix_marketplace_recommendation_evidence_created_at", "created_at"),)

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="marketplace_recommendation.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=80, nullable=False)
    evidence_source: str = Field(max_length=160, nullable=False)
    evidence_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_score: float = Field(sa_column=Column(Float, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceRecommendationReview(SQLModel, table=True):
    __tablename__ = "marketplace_recommendation_review"
    __table_args__ = (SAIndex("ix_marketplace_recommendation_review_reviewed_at", "reviewed_at"),)

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="marketplace_recommendation.id", nullable=False, index=True)
    review_status: str = Field(max_length=24, nullable=False)
    reviewed_by: str = Field(max_length=255, nullable=False)
    reviewed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    review_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
