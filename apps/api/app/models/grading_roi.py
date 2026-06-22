"""P37-03 deterministic grading ROI ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingRoiSnapshot(SQLModel, table=True):
    __tablename__ = "grading_roi_snapshot"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_roi_snapshot_owner_replay"),
        SAIndex(
            "ix_grading_roi_snapshot_owner_inventory_date",
            "owner_user_id",
            "inventory_item_id",
            "snapshot_date",
            "id",
        ),
        SAIndex(
            "ix_grading_roi_snapshot_owner_status",
            "owner_user_id",
            "roi_status",
            "confidence_level",
            "id",
        ),
        SAIndex(
            "ix_grading_roi_snapshot_candidate_target",
            "grading_candidate_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    grading_candidate_id: int | None = Field(default=None, foreign_key="grading_candidate.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    catalog_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)

    target_grader: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)

    raw_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    graded_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    grading_fee_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    shipping_cost_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    insurance_cost_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_turnaround_days: int | None = Field(default=None, nullable=True)
    estimated_total_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_spread_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_net_profit: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_roi_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    liquidity_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    break_even_grade: str | None = Field(default=None, max_length=32, nullable=True)

    roi_status: str = Field(max_length=24, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    evidence_count: int = Field(default=0, nullable=False, ge=0)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    replay_key: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    generation_params_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRoiEvidence(SQLModel, table=True):
    __tablename__ = "grading_roi_evidence"
    __table_args__ = (
        SAIndex("ix_grading_roi_evidence_snapshot_created", "grading_roi_snapshot_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_roi_snapshot_id: int = Field(foreign_key="grading_roi_snapshot.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRoiScenario(SQLModel, table=True):
    __tablename__ = "grading_roi_scenario"
    __table_args__ = (
        SAIndex("ix_grading_roi_scenario_snapshot_name", "grading_roi_snapshot_id", "scenario_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_roi_snapshot_id: int = Field(foreign_key="grading_roi_snapshot.id", nullable=False, index=True)
    scenario_name: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True)
    estimated_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_roi_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    liquidity_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRoiHistory(SQLModel, table=True):
    __tablename__ = "grading_roi_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "checksum",
            name="uq_grading_roi_history_signature",
        ),
        SAIndex(
            "ix_grading_roi_history_issue_target_date",
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    grading_candidate_id: int | None = Field(default=None, foreign_key="grading_candidate.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    roi_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    liquidity_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
