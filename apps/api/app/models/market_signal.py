"""P39-04 deterministic acquisition signal ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketAcquisitionSignalSnapshot(SQLModel, table=True):
    __tablename__ = "market_acquisition_signal_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "market_acquisition_score_snapshot_id",
            "checksum",
            name="uq_market_acquisition_signal_snapshot_signature",
        ),
        SAIndex(
            "ix_market_acquisition_signal_snapshot_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_score_snapshot_id: int = Field(
        foreign_key="market_acquisition_score_snapshot.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
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
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAcquisitionSignal(SQLModel, table=True):
    __tablename__ = "market_acquisition_signal"
    __table_args__ = (
        UniqueConstraint(
            "market_acquisition_signal_snapshot_id",
            "scored_candidate_id",
            name="uq_market_acquisition_signal_snapshot_score",
        ),
        SAIndex(
            "ix_market_acquisition_signal_owner_type_strength",
            "owner_user_id",
            "signal_type",
            "signal_strength",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_signal_snapshot_id: int = Field(
        foreign_key="market_acquisition_signal_snapshot.id",
        nullable=False,
        index=True,
    )
    scored_candidate_id: int = Field(
        foreign_key="market_acquisition_score.id",
        nullable=False,
        index=True,
    )
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    signal_type: str = Field(max_length=40, nullable=False, index=True)
    signal_strength: str = Field(max_length=16, nullable=False, index=True)
    signal_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    signal_reason_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    supporting_factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAcquisitionSignalEvidence(SQLModel, table=True):
    __tablename__ = "market_acquisition_signal_evidence"
    __table_args__ = (
        SAIndex(
            "ix_market_acquisition_signal_evidence_signal_type",
            "market_acquisition_signal_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_signal_id: int = Field(
        foreign_key="market_acquisition_signal.id",
        nullable=False,
        index=True,
    )
    evidence_type: str = Field(max_length=40, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAcquisitionSignalHistory(SQLModel, table=True):
    __tablename__ = "market_acquisition_signal_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "scored_candidate_id",
            "snapshot_date",
            "checksum",
            name="uq_market_acquisition_signal_history_signature",
        ),
        SAIndex(
            "ix_market_acquisition_signal_history_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scored_candidate_id: int = Field(
        foreign_key="market_acquisition_score.id",
        nullable=False,
        index=True,
    )
    signal_type: str = Field(max_length=40, nullable=False, index=True)
    signal_strength: str = Field(max_length=16, nullable=False, index=True)
    signal_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
