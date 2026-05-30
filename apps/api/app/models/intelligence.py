from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index as SAIndex, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class IntelligenceRecommendation(SQLModel, table=True):
    __tablename__ = "intelligence_recommendation"
    __table_args__ = (
        UniqueConstraint("recommendation_uuid", name="uq_intelligence_recommendation_uuid"),
        SAIndex("ix_intelligence_recommendation_type_created", "recommendation_type", "created_at", "id"),
        SAIndex("ix_intelligence_recommendation_status_created", "status", "created_at", "id"),
        SAIndex("ix_intelligence_recommendation_confidence", "confidence_score", "id"),
        SAIndex("ix_intelligence_recommendation_opportunity", "opportunity_score", "id"),
        SAIndex("ix_intelligence_recommendation_priority", "priority_score", "id"),
        SAIndex("ix_intelligence_recommendation_execution_created", "agent_execution_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_uuid: str = Field(max_length=64, nullable=False, index=True)
    agent_execution_id: int = Field(foreign_key="agent_execution.id", nullable=False, index=True)
    recommendation_type: str = Field(max_length=80, nullable=False, index=True)
    title: str = Field(max_length=255, nullable=False)
    description: str = Field(max_length=2000, nullable=False)
    confidence_score: float = Field(sa_column=Column(Float, nullable=False))
    opportunity_score: float = Field(sa_column=Column(Float, nullable=False))
    priority_score: float = Field(sa_column=Column(Float, nullable=False))
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    inventory_title: str = Field(default="", max_length=255, nullable=False)
    status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    recommendation_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IntelligenceEvidence(SQLModel, table=True):
    __tablename__ = "intelligence_evidence"
    __table_args__ = (
        SAIndex("ix_intelligence_evidence_recommendation_created", "recommendation_id", "created_at", "id"),
        SAIndex("ix_intelligence_evidence_type_score", "evidence_type", "evidence_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="intelligence_recommendation.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=80, nullable=False, index=True)
    evidence_source: str = Field(max_length=160, nullable=False)
    evidence_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_score: float = Field(sa_column=Column(Float, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IntelligenceRecommendationReview(SQLModel, table=True):
    __tablename__ = "intelligence_recommendation_review"
    __table_args__ = (
        SAIndex("ix_intelligence_review_recommendation_reviewed", "recommendation_id", "reviewed_at", "id"),
        SAIndex("ix_intelligence_review_status_reviewed", "review_status", "reviewed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="intelligence_recommendation.id", nullable=False, index=True)
    review_status: str = Field(max_length=24, nullable=False, index=True)
    reviewed_by: str = Field(max_length=255, nullable=False)
    reviewed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    review_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
