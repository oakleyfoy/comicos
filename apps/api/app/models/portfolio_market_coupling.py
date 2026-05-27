"""P39-06 deterministic portfolio ↔ market coupling ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Numeric, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioMarketCouplingSnapshot(SQLModel, table=True):
    __tablename__ = "portfolio_market_coupling_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "market_acquisition_opportunity_snapshot_id",
            "snapshot_checksum",
            name="uq_portfolio_market_coupling_snapshot_signature",
        ),
        SAIndex(
            "ix_pm_coupling_snap_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    market_acquisition_opportunity_snapshot_id: int = Field(
        foreign_key="market_acquisition_opportunity_snapshot.id",
        nullable=False,
        index=True,
    )

    portfolio_total_value: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 2), nullable=True)
    )
    portfolio_total_items: int = Field(default=0, nullable=False)
    portfolio_diversification_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    portfolio_concentration_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    portfolio_liquidity_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )

    market_opportunity_count: int = Field(default=0, nullable=False)
    aligned_opportunity_count: int = Field(default=0, nullable=False)
    misaligned_opportunity_count: int = Field(default=0, nullable=False)
    high_fit_market_items: int = Field(default=0, nullable=False)
    low_fit_market_items: int = Field(default=0, nullable=False)

    portfolio_market_alignment_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    diversification_gap_alignment_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    liquidity_gap_alignment_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    concentration_offset_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )

    signal_coverage_ratio: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 8), nullable=True)
    )
    scoring_coverage_ratio: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 8), nullable=True)
    )
    normalization_coverage_ratio: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(18, 8), nullable=True)
    )

    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PortfolioMarketCouplingEdge(SQLModel, table=True):
    __tablename__ = "portfolio_market_coupling_edge"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_market_coupling_snapshot_id",
            "market_normalized_candidate_id",
            "portfolio_item_id",
            "coupling_type",
            "market_acquisition_opportunity_item_id",
            name="uq_pm_coupling_edge_logical",
        ),
        SAIndex("ix_pm_coupling_edge_snap", "portfolio_market_coupling_snapshot_id", "id"),
        SAIndex("ix_pm_coupling_edge_candidate", "market_normalized_candidate_id", "id"),
        SAIndex("ix_pm_coupling_edge_portfolio_item", "portfolio_item_id", "id"),
        SAIndex("ix_pm_coupling_edge_type_str", "coupling_type", "coupling_strength", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_market_coupling_snapshot_id: int = Field(
        foreign_key="portfolio_market_coupling_snapshot.id",
        nullable=False,
        index=True,
    )
    market_normalized_candidate_id: int = Field(
        foreign_key="market_acquisition_normalized_candidate.id",
        nullable=False,
        index=True,
    )
    market_acquisition_opportunity_item_id: int = Field(
        foreign_key="market_acquisition_opportunity_item.id",
        nullable=False,
        index=True,
    )
    portfolio_item_id: int | None = Field(
        default=None, foreign_key="portfolio_item.id", nullable=True, index=True
    )

    coupling_type: str = Field(max_length=28, nullable=False, index=True)
    coupling_strength: str = Field(max_length=16, nullable=False, index=True)

    coupling_score: int = Field(default=0, nullable=False)

    explanation_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))

    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PortfolioMarketCouplingEvidence(SQLModel, table=True):
    __tablename__ = "portfolio_market_coupling_evidence"
    __table_args__ = (
        SAIndex(
            "ix_pm_coupling_evidence_snap_type",
            "portfolio_market_coupling_snapshot_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_market_coupling_snapshot_id: int = Field(
        foreign_key="portfolio_market_coupling_snapshot.id",
        nullable=False,
        index=True,
    )
    evidence_type: str = Field(max_length=28, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PortfolioMarketCouplingHistory(SQLModel, table=True):
    __tablename__ = "portfolio_market_coupling_history"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_market_coupling_snapshot_id",
            name="uq_pm_coupling_history_snapshot_unique",
        ),
        SAIndex("ix_pm_coupling_hist_owner_date", "owner_user_id", "snapshot_date", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_market_coupling_snapshot_id: int = Field(
        foreign_key="portfolio_market_coupling_snapshot.id",
        nullable=False,
        index=True,
    )

    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    alignment_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    market_opportunity_count: int = Field(default=0, nullable=False)
    high_fit_market_items: int = Field(default=0, nullable=False)

    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
