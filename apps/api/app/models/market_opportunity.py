"""P39-05 deterministic acquisition opportunity snapshot ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Numeric, UniqueConstraint
from sqlalchemy import Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketAcquisitionOpportunitySnapshot(SQLModel, table=True):
    __tablename__ = "market_acquisition_opportunity_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "market_acquisition_signal_snapshot_id",
            "snapshot_checksum",
            name="uq_market_acquisition_opportunity_snapshot_signature",
        ),
        SAIndex(
            "ix_market_acquisition_opportunity_snapshot_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_signal_snapshot_id: int = Field(
        foreign_key="market_acquisition_signal_snapshot.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int | None = Field(
        default=None, foreign_key="user.id", nullable=True, index=True
    )
    opportunity_classification: str = Field(max_length=40, nullable=False, index=True)
    total_candidates: int = Field(default=0, nullable=False)
    total_signals: int = Field(default=0, nullable=False)
    elite_signal_count: int = Field(default=0, nullable=False)
    high_signal_count: int = Field(default=0, nullable=False)
    medium_signal_count: int = Field(default=0, nullable=False)
    low_signal_count: int = Field(default=0, nullable=False)
    value_dislocation_count: int = Field(default=0, nullable=False)
    liquidity_opportunity_count: int = Field(default=0, nullable=False)
    portfolio_gap_fill_count: int = Field(default=0, nullable=False)
    concentration_reduction_count: int = Field(default=0, nullable=False)
    grading_upside_count: int = Field(default=0, nullable=False)
    redundant_asset_count: int = Field(default=0, nullable=False)
    high_risk_asset_count: int = Field(default=0, nullable=False)
    estimated_portfolio_gap_coverage: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    estimated_liquidity_gain: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    estimated_diversification_gain: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    estimated_risk_adjustment: Decimal = Field(
        default=Decimal("0.00"),
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    avg_signal_strength: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    avg_acquisition_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    avg_confidence_level: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    avg_risk_level: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 4), nullable=True)
    )
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class MarketAcquisitionOpportunityItem(SQLModel, table=True):
    __tablename__ = "market_acquisition_opportunity_item"
    __table_args__ = (
        UniqueConstraint(
            "market_acquisition_opportunity_snapshot_id",
            "market_acquisition_signal_id",
            name="uq_market_acquisition_opportunity_item_signal",
        ),
        SAIndex(
            "ix_market_acquisition_opportunity_item_owner_filters",
            "owner_user_id",
            "signal_type",
            "signal_strength",
            "risk_level",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_opportunity_snapshot_id: int = Field(
        foreign_key="market_acquisition_opportunity_snapshot.id",
        nullable=False,
        index=True,
    )
    candidate_id: int = Field(
        foreign_key="market_acquisition_normalized_candidate.id",
        nullable=False,
        index=True,
    )
    market_acquisition_signal_id: int = Field(
        foreign_key="market_acquisition_signal.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int | None = Field(
        default=None, foreign_key="user.id", nullable=True, index=True
    )
    signal_type: str = Field(max_length=40, nullable=False, index=True)
    signal_strength: str = Field(max_length=16, nullable=False, index=True)
    acquisition_score: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True)
    )
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    contribution_weight: Decimal = Field(
        sa_column=Column(Numeric(10, 6), nullable=False),
    )
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class MarketAcquisitionOpportunityEvidence(SQLModel, table=True):
    __tablename__ = "market_acquisition_opportunity_evidence"
    __table_args__ = (
        SAIndex(
            "ix_market_acquisition_opportunity_evidence_snap_type",
            "market_acquisition_opportunity_snapshot_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_opportunity_snapshot_id: int = Field(
        foreign_key="market_acquisition_opportunity_snapshot.id",
        nullable=False,
        index=True,
    )
    evidence_type: str = Field(max_length=40, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class MarketAcquisitionOpportunityHistory(SQLModel, table=True):
    __tablename__ = "market_acquisition_opportunity_history"
    __table_args__ = (
        SAIndex(
            "ix_market_acquisition_opportunity_history_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int | None = Field(
        default=None, foreign_key="user.id", nullable=True, index=True
    )
    market_acquisition_opportunity_snapshot_id: int = Field(
        foreign_key="market_acquisition_opportunity_snapshot.id",
        nullable=False,
        index=True,
    )
    snapshot_checksum: str = Field(max_length=64, nullable=False, index=True)
    total_candidates: int = Field(default=0, nullable=False)
    elite_signal_count: int = Field(default=0, nullable=False)
    high_signal_count: int = Field(default=0, nullable=False)
    estimated_portfolio_gap_coverage: Decimal = Field(
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    estimated_diversification_gain: Decimal = Field(
        sa_column=Column(Numeric(12, 2), nullable=False),
    )
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
