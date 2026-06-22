"""P37-06 deterministic grading recommendation ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingRecommendation(SQLModel, table=True):
    __tablename__ = "grading_recommendation"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_recommendation_owner_replay"),
        SAIndex(
            "ix_grading_recommendation_owner_status",
            "owner_user_id",
            "recommendation_status",
            "recommended_action",
            "id",
        ),
        SAIndex(
            "ix_grading_recommendation_owner_strength",
            "owner_user_id",
            "recommendation_strength",
            "risk_level",
            "id",
        ),
        SAIndex(
            "ix_grading_recommendation_scope_date",
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    grading_candidate_id: int | None = Field(default=None, foreign_key="grading_candidate.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    catalog_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)
    recommended_action: str = Field(max_length=24, nullable=False, index=True)
    recommended_grader: str | None = Field(default=None, max_length=16, nullable=True, index=True)
    recommended_grade_target: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    expected_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    liquidity_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    estimated_net_profit: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_total_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    confidence_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    recommendation_strength: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    recommendation_status: str = Field(max_length=16, nullable=False, index=True)
    rationale_summary: str = Field(sa_column=Column(Text, nullable=False))
    warning_flags_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    evidence_count: int = Field(default=0, nullable=False)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRecommendationEvidence(SQLModel, table=True):
    __tablename__ = "grading_recommendation_evidence"
    __table_args__ = (
        SAIndex(
            "ix_grading_recommendation_evidence_recommendation_created",
            "grading_recommendation_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_recommendation_id: int = Field(foreign_key="grading_recommendation.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRecommendationScenario(SQLModel, table=True):
    __tablename__ = "grading_recommendation_scenario"
    __table_args__ = (
        SAIndex(
            "ix_grading_recommendation_scenario_recommendation_name",
            "grading_recommendation_id",
            "scenario_name",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_recommendation_id: int = Field(foreign_key="grading_recommendation.id", nullable=False, index=True)
    scenario_name: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True)
    estimated_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    confidence_modifier: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRecommendationHistory(SQLModel, table=True):
    __tablename__ = "grading_recommendation_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "recommended_action",
            "recommended_grader",
            "snapshot_date",
            "checksum",
            name="uq_grading_recommendation_history_signature",
        ),
        SAIndex(
            "ix_grading_recommendation_history_scope_date",
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    grading_candidate_id: int | None = Field(default=None, foreign_key="grading_candidate.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    recommended_action: str = Field(max_length=24, nullable=False, index=True)
    recommended_grader: str | None = Field(default=None, max_length=16, nullable=True, index=True)
    recommendation_strength: str = Field(max_length=16, nullable=False, index=True)
    confidence_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
