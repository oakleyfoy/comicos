"""P37-02 deterministic raw-vs-graded spread registry."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingSpreadSnapshot(SQLModel, table=True):
    __tablename__ = "grading_spread_snapshot"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_spread_snapshot_owner_replay"),
        SAIndex(
            "ix_grading_spread_snapshot_owner_inventory_date",
            "owner_user_id",
            "inventory_item_id",
            "snapshot_date",
            "id",
        ),
        SAIndex(
            "ix_grading_spread_snapshot_owner_status",
            "owner_user_id",
            "spread_status",
            "confidence_level",
            "id",
        ),
        SAIndex(
            "ix_grading_spread_snapshot_issue_target",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    catalog_issue_id: int | None = Field(default=None, foreign_key="catalog_issue.id", nullable=True, index=True)

    target_grader: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)

    raw_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    graded_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    grading_cost_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_spread_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    estimated_spread_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    estimated_net_upside: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    liquidity_adjusted_upside: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))

    spread_status: str = Field(max_length=24, nullable=False, index=True)
    liquidity_modifier: str = Field(max_length=16, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    evidence_count: int = Field(default=0, nullable=False, ge=0)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    replay_key: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    generation_params_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSpreadEvidence(SQLModel, table=True):
    __tablename__ = "grading_spread_evidence"
    __table_args__ = (
        SAIndex(
            "ix_grading_spread_evidence_snapshot_created",
            "grading_spread_snapshot_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_spread_snapshot_id: int = Field(
        foreign_key="grading_spread_snapshot.id",
        nullable=False,
        index=True,
    )
    evidence_type: str = Field(max_length=24, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSpreadBand(SQLModel, table=True):
    __tablename__ = "grading_spread_band"
    __table_args__ = (
        SAIndex("ix_grading_spread_band_target", "target_grader", "target_grade", "status_label", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    lower_bound_pct: Decimal = Field(sa_column=Column(Numeric(18, 8), nullable=False))
    upper_bound_pct: Decimal = Field(sa_column=Column(Numeric(18, 8), nullable=False))
    status_label: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingSpreadHistory(SQLModel, table=True):
    __tablename__ = "grading_spread_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "inventory_item_id",
            "canonical_comic_issue_id",
            "target_grader",
            "target_grade",
            "snapshot_date",
            "checksum",
            name="uq_grading_spread_history_signature",
        ),
        SAIndex(
            "ix_grading_spread_history_issue_target_date",
            "owner_user_id",
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
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    target_grader: str = Field(max_length=16, nullable=False, index=True)
    target_grade: str | None = Field(default=None, max_length=32, nullable=True, index=True)
    spread_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    spread_pct: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
