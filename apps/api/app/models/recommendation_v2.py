from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Text, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class RecommendationRunV2(SQLModel, table=True):
    __tablename__ = "recommendation_run_v2"
    __table_args__ = (
        UniqueConstraint("run_uuid", name="uq_recommendation_run_v2_uuid"),
        SAIndex("ix_recommendation_run_v2_owner", "owner_user_id", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    run_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(default="RUNNING", max_length=24, nullable=False, index=True)
    issues_scored: int = Field(default=0, nullable=False)
    variants_scored: int = Field(default=0, nullable=False)
    recommendations_created: int = Field(default=0, nullable=False)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class RecommendationScoreV2(SQLModel, table=True):
    __tablename__ = "recommendation_score_v2"
    __table_args__ = (
        SAIndex("ix_recommendation_score_v2_owner_tier", "owner_user_id", "recommendation_tier", "total_score", "id"),
        SAIndex("ix_recommendation_score_v2_issue", "release_issue_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    recommendation_run_id: int = Field(foreign_key="recommendation_run_v2.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    release_variant_id: int | None = Field(default=None, foreign_key="release_variant.id", nullable=True, index=True)
    total_score: float = Field(nullable=False, index=True)
    recommendation_tier: str = Field(max_length=24, nullable=False, index=True)
    recommendation_type: str = Field(max_length=48, nullable=False, index=True)
    confidence_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RecommendationScoreComponentV2(SQLModel, table=True):
    __tablename__ = "recommendation_score_component_v2"
    __table_args__ = (SAIndex("ix_rec_score_component_v2_score", "recommendation_score_id", "component_name"),)

    id: int | None = Field(default=None, primary_key=True)
    recommendation_score_id: int = Field(foreign_key="recommendation_score_v2.id", nullable=False, index=True)
    component_name: str = Field(max_length=64, nullable=False, index=True)
    component_score: float = Field(nullable=False)
    component_weight: float = Field(nullable=False)
    explanation: str = Field(default="", sa_column=Column(Text, nullable=False))


class RecommendationDecisionV2(SQLModel, table=True):
    __tablename__ = "recommendation_decision_v2"
    __table_args__ = (SAIndex("ix_recommendation_decision_v2_score", "recommendation_score_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    recommendation_score_id: int = Field(foreign_key="recommendation_score_v2.id", nullable=False, index=True)
    decision_summary: str = Field(sa_column=Column(Text, nullable=False))
    primary_reason: str = Field(sa_column=Column(Text, nullable=False))
    risk_note: str = Field(default="", sa_column=Column(Text, nullable=False))
    suggested_action: str = Field(sa_column=Column(Text, nullable=False))
    suggested_quantity: int = Field(default=1, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
