from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Index as SAIndex, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_recommendation_uuid() -> str:
    return str(uuid4())


def generate_execution_uuid() -> str:
    return str(uuid4())


class DealerRecommendation(SQLModel, table=True):
    __tablename__ = "dealer_recommendation"
    __table_args__ = (
        UniqueConstraint("recommendation_uuid", name="uq_dealer_recommendation_uuid"),
        SAIndex("ix_dealer_recommendation_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    agent_execution_id: int | None = Field(default=None, foreign_key="dealer_copilot_execution.id", nullable=True, index=True)
    recommendation_uuid: str = Field(default_factory=generate_recommendation_uuid, max_length=64, nullable=False, index=True)
    recommendation_type: str = Field(max_length=80, nullable=False, index=True)
    asset_type: str = Field(max_length=80, nullable=False, index=True)
    asset_id: int | None = Field(default=None, nullable=True, index=True)
    title: str = Field(max_length=255, nullable=False)
    description: str = Field(sa_column=Column(String, nullable=False))
    confidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    priority_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    recommendation_status: str = Field(default="OPEN", max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerRecommendationEvidence(SQLModel, table=True):
    __tablename__ = "dealer_recommendation_evidence"
    __table_args__ = (
        SAIndex("ix_dealer_recommendation_evidence_recommendation_created", "recommendation_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="dealer_recommendation.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=80, nullable=False, index=True)
    evidence_source: str = Field(max_length=160, nullable=False)
    evidence_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    evidence_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerRecommendationReview(SQLModel, table=True):
    __tablename__ = "dealer_recommendation_review"
    __table_args__ = (
        SAIndex("ix_dealer_recommendation_review_recommendation_reviewed", "recommendation_id", "reviewed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="dealer_recommendation.id", nullable=False, index=True)
    review_status: str = Field(max_length=24, nullable=False, index=True)
    reviewed_by: str = Field(max_length=255, nullable=False)
    reviewed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    review_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class DealerOpportunityScore(SQLModel, table=True):
    __tablename__ = "dealer_opportunity_score"
    __table_args__ = (
        SAIndex("ix_dealer_opportunity_score_owner_calculated", "owner_user_id", "calculated_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    asset_type: str = Field(max_length=80, nullable=False, index=True)
    asset_id: int = Field(nullable=False, index=True)
    opportunity_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    risk_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0, index=True))
    forecast_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    demand_score: float = Field(sa_column=Column(Float, nullable=False, default=0.0))
    grading_score: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    calculated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DealerCopilotExecution(SQLModel, table=True):
    __tablename__ = "dealer_copilot_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_dealer_copilot_execution_uuid"),
        SAIndex("ix_dealer_copilot_execution_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    agent_code: str = Field(max_length=80, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_execution_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
