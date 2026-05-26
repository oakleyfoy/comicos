"""P38-03 portfolio-level deterministic liquidity allocation intelligence (observational)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, Date, DateTime, Index as SAIndex, JSON, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioLiquiditySnapshot(SQLModel, table=True):
    __tablename__ = "portfolio_liquidity_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            name="uq_portfolio_liquidity_snapshot_replay_signature",
        ),
        SAIndex("ix_portfolio_liquidity_snapshot_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex(
            "ix_portfolio_liquidity_snapshot_owner_status",
            "owner_user_id",
            "liquidity_balance_status",
        ),
        SAIndex("ix_portfolio_liquidity_snapshot_owner_scope", "owner_user_id", "generation_scope_key"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    generation_scope_key: str = Field(max_length=64, nullable=False)
    replay_key: str = Field(default="", max_length=128, nullable=False, index=True)

    total_portfolio_fmv: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    liquid_portfolio_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    illiquid_portfolio_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    liquidity_weighted_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    liquidity_efficiency_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    liquidity_drag_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    concentration_risk_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    dead_capital_estimate: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    liquidity_balance_status: str = Field(max_length=24, nullable=False, index=True)

    high_liquidity_count: int = Field(default=0, nullable=False)
    medium_liquidity_count: int = Field(default=0, nullable=False)
    low_liquidity_count: int = Field(default=0, nullable=False)
    illiquid_count: int = Field(default=0, nullable=False)

    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioLiquidityBucket(SQLModel, table=True):
    __tablename__ = "portfolio_liquidity_bucket"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_liquidity_snapshot_id",
            "liquidity_bucket",
            name="uq_portfolio_liquidity_bucket_signature",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_liquidity_snapshot_id: int = Field(foreign_key="portfolio_liquidity_snapshot.id", nullable=False, index=True)
    liquidity_bucket: str = Field(max_length=16, nullable=False)
    item_count: int = Field(default=0, nullable=False)
    total_fmv: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    weighted_liquidity_value: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    percentage_of_portfolio: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 4), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioLiquidityEvidence(SQLModel, table=True):
    __tablename__ = "portfolio_liquidity_evidence"
    __table_args__ = (
        SAIndex(
            "ix_portfolio_liquidity_evidence_snapshot_type",
            "portfolio_liquidity_snapshot_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_liquidity_snapshot_id: int = Field(foreign_key="portfolio_liquidity_snapshot.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=64, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioLiquidityHistory(SQLModel, table=True):
    __tablename__ = "portfolio_liquidity_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "generation_scope_key",
            "snapshot_date",
            "replay_key",
            "checksum",
            name="uq_portfolio_liquidity_history_replay_checksum",
        ),
        SAIndex("ix_portfolio_liquidity_history_owner_date", "owner_user_id", "snapshot_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    generation_scope_key: str = Field(max_length=64, nullable=False)
    replay_key: str = Field(default="", max_length=128, nullable=False)

    liquidity_efficiency_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    liquidity_drag_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    concentration_risk_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(6, 2), nullable=True))
    dead_capital_estimate: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    liquidity_balance_status: str = Field(max_length=24, nullable=False)

    checksum: str = Field(max_length=64, nullable=False)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
