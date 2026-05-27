"""P39-03 deterministic acquisition scoring ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketAcquisitionScoreSnapshot(SQLModel, table=True):
    __tablename__ = "market_acquisition_score_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "snapshot_date",
            "checksum",
            name="uq_market_acquisition_score_snapshot_owner_signature",
        ),
        SAIndex(
            "ix_market_acquisition_score_snapshot_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    total_candidates_scored: int = Field(default=0, nullable=False)
    avg_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    avg_liquidity_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    avg_grading_upside_score: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    high_value_count: int = Field(default=0, nullable=False)
    strong_buy_count: int = Field(default=0, nullable=False)
    buy_count: int = Field(default=0, nullable=False)
    watch_count: int = Field(default=0, nullable=False)
    ignore_count: int = Field(default=0, nullable=False)
    portfolio_alignment_score: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    liquidity_alignment_score: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    diversification_alignment_score: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAcquisitionScore(SQLModel, table=True):
    __tablename__ = "market_acquisition_score"
    __table_args__ = (
        UniqueConstraint(
            "market_acquisition_score_snapshot_id",
            "normalized_candidate_id",
            name="uq_market_acquisition_score_snapshot_candidate",
        ),
        SAIndex(
            "ix_market_acquisition_score_owner_label",
            "owner_user_id",
            "recommendation_label",
            "final_rank_score",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    market_acquisition_score_snapshot_id: int = Field(
        foreign_key="market_acquisition_score_snapshot.id",
        nullable=False,
        index=True,
    )
    normalized_candidate_id: int = Field(
        foreign_key="market_acquisition_normalized_candidate.id",
        nullable=False,
        index=True,
    )
    canonical_comic_issue_id: int | None = Field(
        default=None,
        foreign_key="comic_issue.id",
        nullable=True,
        index=True,
    )
    owner_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    acquisition_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    portfolio_fit_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    liquidity_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    grading_upside_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    concentration_reduction_score: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    diversification_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    risk_penalty_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    final_rank_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    score_breakdown_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    recommendation_label: str = Field(max_length=24, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAcquisitionScoreEvidence(SQLModel, table=True):
    __tablename__ = "market_acquisition_score_evidence"
    __table_args__ = (
        SAIndex(
            "ix_market_acquisition_score_evidence_score_type",
            "score_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    score_id: int = Field(foreign_key="market_acquisition_score.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=40, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketAcquisitionScoreHistory(SQLModel, table=True):
    __tablename__ = "market_acquisition_score_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "normalized_candidate_id",
            "snapshot_date",
            "checksum",
            name="uq_market_acquisition_score_history_signature",
        ),
        SAIndex(
            "ix_market_acquisition_score_history_owner_date",
            "owner_user_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    normalized_candidate_id: int = Field(
        foreign_key="market_acquisition_normalized_candidate.id",
        nullable=False,
        index=True,
    )
    acquisition_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    recommendation_label: str = Field(max_length=24, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
