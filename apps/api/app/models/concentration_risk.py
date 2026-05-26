"""P38-05 deterministic portfolio concentration-risk intelligence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConcentrationRiskSnapshot(SQLModel, table=True):
    __tablename__ = "concentration_risk_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "concentration_type",
            "concentration_key",
            "snapshot_date",
            "replay_key",
            name="uq_concentration_risk_snapshot_replay",
        ),
        SAIndex("ix_concentration_risk_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex(
            "ix_concentration_risk_owner_status",
            "owner_user_id",
            "exposure_status",
            "concentration_type",
            "id",
        ),
        SAIndex(
            "ix_concentration_risk_scope_key",
            "owner_user_id",
            "portfolio_id",
            "concentration_type",
            "concentration_key",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    concentration_type: str = Field(max_length=32, nullable=False, index=True)
    concentration_key: str = Field(max_length=256, nullable=False, index=True)
    replay_key: str = Field(default="", max_length=128, nullable=False, index=True)

    total_item_count: int = Field(default=0, nullable=False)
    total_fmv_amount: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    percentage_of_portfolio: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    concentration_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    liquidity_weighted_concentration: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(10, 2), nullable=True)
    )
    exposure_status: str = Field(max_length=24, nullable=False, index=True)
    diversification_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))

    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConcentrationRiskEvidence(SQLModel, table=True):
    __tablename__ = "concentration_risk_evidence"
    __table_args__ = (
        SAIndex(
            "ix_concentration_risk_evidence_snapshot_type",
            "concentration_risk_snapshot_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    concentration_risk_snapshot_id: int = Field(
        foreign_key="concentration_risk_snapshot.id", nullable=False, index=True
    )
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConcentrationRiskFactor(SQLModel, table=True):
    __tablename__ = "concentration_risk_factor"
    __table_args__ = (
        UniqueConstraint(
            "concentration_risk_snapshot_id",
            "factor_key",
            name="uq_concentration_risk_factor_snapshot_key",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    concentration_risk_snapshot_id: int = Field(
        foreign_key="concentration_risk_snapshot.id", nullable=False, index=True
    )
    factor_key: str = Field(max_length=40, nullable=False, index=True)
    factor_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    weighting: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 8), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConcentrationRiskHistory(SQLModel, table=True):
    __tablename__ = "concentration_risk_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "concentration_type",
            "concentration_key",
            "snapshot_date",
            "checksum",
            name="uq_concentration_risk_history_signature",
        ),
        SAIndex("ix_concentration_risk_history_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex(
            "ix_concentration_risk_history_scope_key",
            "owner_user_id",
            "portfolio_id",
            "concentration_type",
            "concentration_key",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    concentration_type: str = Field(max_length=32, nullable=False, index=True)
    concentration_key: str = Field(max_length=256, nullable=False, index=True)
    exposure_status: str = Field(max_length=24, nullable=False, index=True)
    concentration_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    diversification_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
