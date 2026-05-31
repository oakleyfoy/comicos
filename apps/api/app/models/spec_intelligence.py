from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, DateTime, Text, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class SpecScore(SQLModel, table=True):
    __tablename__ = "spec_score"
    __table_args__ = (
        SAIndex("ix_spec_score_issue_created", "release_issue_id", "created_at", "id"),
        SAIndex("ix_spec_score_value_created", "score_value", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    score_value: float = Field(nullable=False, index=True)
    score_grade: str = Field(max_length=16, nullable=False, index=True)
    confidence_score: float = Field(nullable=False, index=True)
    score_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class SpecRecommendation(SQLModel, table=True):
    __tablename__ = "spec_recommendation"
    __table_args__ = (
        UniqueConstraint("recommendation_uuid", name="uq_spec_recommendation_uuid"),
        SAIndex("ix_spec_recommendation_issue_created", "release_issue_id", "created_at", "id"),
        SAIndex("ix_spec_recommendation_type_created", "recommendation_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    recommendation_type: str = Field(max_length=24, nullable=False, index=True)
    recommendation_score: float = Field(nullable=False)
    confidence_score: float = Field(nullable=False)
    recommendation_reason: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class SpecRecommendationReview(SQLModel, table=True):
    __tablename__ = "spec_recommendation_review"
    __table_args__ = (
        SAIndex("ix_spec_recommendation_review_rec_created", "recommendation_id", "reviewed_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    recommendation_id: int = Field(foreign_key="spec_recommendation.id", nullable=False, index=True)
    review_status: str = Field(max_length=24, nullable=False, index=True)
    reviewed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    review_notes: str = Field(default="", sa_column=Column(Text, nullable=False))


class WeeklyBuyList(SQLModel, table=True):
    __tablename__ = "weekly_buy_list"
    __table_args__ = (
        UniqueConstraint("list_uuid", name="uq_weekly_buy_list_uuid"),
        SAIndex("ix_weekly_buy_list_owner_week", "owner_user_id", "week_start_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    list_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    week_start_date: date = Field(nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class WeeklyBuyListItem(SQLModel, table=True):
    __tablename__ = "weekly_buy_list_item"
    __table_args__ = (
        SAIndex("ix_weekly_buy_list_item_list_rank", "weekly_buy_list_id", "ranking_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    weekly_buy_list_id: int = Field(foreign_key="weekly_buy_list.id", nullable=False, index=True)
    release_issue_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    buy_category: str = Field(max_length=24, nullable=False, index=True)
    ranking_score: float = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


class SpecAgentExecution(SQLModel, table=True):
    __tablename__ = "spec_agent_execution"
    __table_args__ = (
        UniqueConstraint("execution_uuid", name="uq_spec_agent_execution_uuid"),
        SAIndex("ix_spec_agent_execution_owner_started", "owner_user_id", "started_at", "id"),
        SAIndex("ix_spec_agent_execution_agent_started", "agent_code", "started_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    agent_code: str = Field(max_length=64, nullable=False, index=True)
    execution_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    status: str = Field(max_length=24, nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
