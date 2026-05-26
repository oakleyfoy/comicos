"""P38-02 deterministic duplicate & consolidation intelligence (observational only)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DuplicateCluster(SQLModel, table=True):
    __tablename__ = "duplicate_cluster"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "generation_batch_checksum",
            "cluster_type",
            "cluster_key",
            name="uq_duplicate_cluster_batch_type_key",
        ),
        SAIndex("ix_duplicate_cluster_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex("ix_duplicate_cluster_owner_batch", "owner_user_id", "generation_batch_checksum", "id"),
        SAIndex("ix_duplicate_cluster_owner_status", "owner_user_id", "duplication_status", "id"),
        SAIndex("ix_duplicate_cluster_owner_type", "owner_user_id", "cluster_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    canonical_comic_issue_id: int | None = Field(
        default=None,
        foreign_key="comic_issue.id",
        nullable=True,
        index=True,
    )
    cluster_key: str = Field(max_length=256, nullable=False, index=True)
    cluster_type: str = Field(max_length=32, nullable=False, index=True)
    generation_batch_checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_key: str = Field(default="", max_length=128, nullable=False, index=True)

    total_item_count: int = Field(default=0, nullable=False)
    graded_item_count: int = Field(default=0, nullable=False)
    raw_item_count: int = Field(default=0, nullable=False)
    total_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    total_cost_basis_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))

    liquidity_profile: str = Field(max_length=16, nullable=False, index=True)
    duplication_status: str = Field(max_length=24, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DuplicateClusterItem(SQLModel, table=True):
    __tablename__ = "duplicate_cluster_item"
    __table_args__ = (
        UniqueConstraint("duplicate_cluster_id", "inventory_item_id", name="uq_dup_cluster_item_cluster_inv"),
        SAIndex("ix_duplicate_cluster_item_cluster", "duplicate_cluster_id", "id"),
        SAIndex("ix_duplicate_cluster_item_inventory", "inventory_item_id", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    duplicate_cluster_id: int = Field(foreign_key="duplicate_cluster.id", nullable=False, index=True)
    inventory_item_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)

    grading_status: str = Field(max_length=24, nullable=False, index=True)
    estimated_strength_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    liquidity_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    current_fmv: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    acquisition_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(14, 2), nullable=True))
    recommendation_priority: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DuplicateConsolidationRecommendation(SQLModel, table=True):
    __tablename__ = "duplicate_consolidation_recommendation"
    __table_args__ = (
        UniqueConstraint("duplicate_cluster_id", name="uq_dup_consolidation_one_per_cluster"),
        SAIndex("ix_dup_consolidation_owner_status", "owner_user_id", "recommendation_status", "id"),
        SAIndex("ix_dup_consolidation_owner_action", "owner_user_id", "recommendation_action", "id"),
        SAIndex("ix_dup_consolidation_owner_date", "owner_user_id", "snapshot_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    duplicate_cluster_id: int = Field(foreign_key="duplicate_cluster.id", nullable=False, index=True)
    generation_batch_checksum: str = Field(max_length=64, nullable=False, index=True)
    recommendation_action: str = Field(max_length=32, nullable=False, index=True)
    rationale_summary: str = Field(sa_column=Column(Text, nullable=False))
    expected_capital_reduction: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(18, 2), nullable=True),
    )
    estimated_liquidity_improvement: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    estimated_portfolio_efficiency_gain: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    recommendation_status: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    replay_key: str = Field(default="", max_length=128, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DuplicateHistorySnapshot(SQLModel, table=True):
    __tablename__ = "duplicate_history_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "cluster_key",
            "snapshot_date",
            "replay_key",
            "generation_batch_checksum",
            name="uq_duplicate_history_key_date_batch",
        ),
        SAIndex("ix_duplicate_history_owner_date", "owner_user_id", "snapshot_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    cluster_key: str = Field(max_length=256, nullable=False, index=True)
    cluster_type: str = Field(max_length=32, nullable=False, index=True)
    total_item_count: int = Field(default=0, nullable=False)
    total_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    duplication_status: str = Field(max_length=24, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False)
    generation_batch_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    replay_key: str = Field(default="", max_length=128, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
