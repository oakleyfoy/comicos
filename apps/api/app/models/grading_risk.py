"""P37-07 deterministic grading risk and confidence ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GradingRiskSnapshot(SQLModel, table=True):
    __tablename__ = "grading_risk_snapshot"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "replay_key", name="uq_grading_risk_snapshot_owner_replay"),
        SAIndex(
            "ix_grading_risk_snapshot_owner_levels",
            "owner_user_id",
            "overall_risk_level",
            "overall_confidence_level",
            "id",
        ),
        SAIndex(
            "ix_grading_risk_snapshot_scope_date",
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
    recommendation_id: int | None = Field(default=None, foreign_key="grading_recommendation.id", nullable=True, index=True)
    overall_risk_level: str = Field(max_length=16, nullable=False, index=True)
    overall_confidence_level: str = Field(max_length=16, nullable=False, index=True)
    liquidity_risk_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    spread_volatility_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    roi_volatility_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    grader_variability_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    reconciliation_variance_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    market_stability_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    evidence_strength_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    risk_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    confidence_weight: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    warning_flags_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    evidence_count: int = Field(default=0, nullable=False)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class GradingRiskEvidence(SQLModel, table=True):
    __tablename__ = "grading_risk_evidence"
    __table_args__ = (
        SAIndex(
            "ix_grading_risk_evidence_snapshot_created",
            "grading_risk_snapshot_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_risk_snapshot_id: int = Field(foreign_key="grading_risk_snapshot.id", nullable=False, index=True)
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ConfidenceFactorSnapshot(SQLModel, table=True):
    __tablename__ = "confidence_factor_snapshot"
    __table_args__ = (
        SAIndex(
            "ix_confidence_factor_snapshot_risk_factor",
            "grading_risk_snapshot_id",
            "factor_key",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    grading_risk_snapshot_id: int = Field(foreign_key="grading_risk_snapshot.id", nullable=False, index=True)
    factor_key: str = Field(max_length=40, nullable=False, index=True)
    factor_score: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    weighting: Decimal = Field(sa_column=Column(Numeric(10, 8), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RiskHistory(SQLModel, table=True):
    __tablename__ = "risk_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "grading_candidate_id",
            "inventory_item_id",
            "overall_risk_level",
            "overall_confidence_level",
            "snapshot_date",
            "checksum",
            name="uq_risk_history_signature",
        ),
        SAIndex(
            "ix_risk_history_scope_date",
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
    overall_risk_level: str = Field(max_length=16, nullable=False, index=True)
    overall_confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_adjusted_roi: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
