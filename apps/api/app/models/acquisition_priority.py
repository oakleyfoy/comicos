"""P38-06 deterministic portfolio acquisition-priority intelligence."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcquisitionPrioritySnapshot(SQLModel, table=True):
    __tablename__ = "acquisition_priority_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "canonical_comic_issue_id",
            "acquisition_category",
            "snapshot_date",
            "replay_key",
            name="uq_acquisition_priority_snapshot_replay",
        ),
        SAIndex("ix_acquisition_priority_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex(
            "ix_acquisition_priority_owner_priority",
            "owner_user_id",
            "acquisition_priority",
            "acquisition_category",
            "id",
        ),
        SAIndex(
            "ix_acquisition_priority_owner_issue_category",
            "owner_user_id",
            "canonical_comic_issue_id",
            "acquisition_category",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    acquisition_category: str = Field(max_length=32, nullable=False, index=True)
    acquisition_priority: str = Field(max_length=16, nullable=False, index=True)
    replay_key: str = Field(default="", max_length=128, nullable=False, index=True)

    portfolio_impact_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    diversification_impact: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    liquidity_impact: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    grading_upside_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    duplication_risk: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    concentration_reduction_score: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    estimated_capital_efficiency: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    recommendation_strength: str = Field(max_length=16, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    rationale_summary: str = Field(max_length=600, nullable=False)
    warning_flags_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))

    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AcquisitionPriorityEvidence(SQLModel, table=True):
    __tablename__ = "acquisition_priority_evidence"
    __table_args__ = (
        SAIndex(
            "ix_acquisition_priority_evidence_snapshot_type",
            "acquisition_priority_snapshot_id",
            "evidence_type",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    acquisition_priority_snapshot_id: int = Field(
        foreign_key="acquisition_priority_snapshot.id", nullable=False, index=True
    )
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AcquisitionPriorityScenario(SQLModel, table=True):
    __tablename__ = "acquisition_priority_scenario"
    __table_args__ = (
        UniqueConstraint(
            "acquisition_priority_snapshot_id",
            "scenario_name",
            name="uq_acquisition_priority_scenario_snapshot_name",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    acquisition_priority_snapshot_id: int = Field(
        foreign_key="acquisition_priority_snapshot.id", nullable=False, index=True
    )
    scenario_name: str = Field(max_length=16, nullable=False, index=True)
    projected_liquidity_impact: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    projected_diversification_impact: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    projected_portfolio_efficiency: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 2), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AcquisitionPriorityHistory(SQLModel, table=True):
    __tablename__ = "acquisition_priority_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "canonical_comic_issue_id",
            "acquisition_category",
            "snapshot_date",
            "checksum",
            name="uq_acquisition_priority_history_signature",
        ),
        SAIndex("ix_acquisition_priority_history_owner_date", "owner_user_id", "snapshot_date", "id"),
        SAIndex(
            "ix_acquisition_priority_history_owner_issue_category",
            "owner_user_id",
            "canonical_comic_issue_id",
            "acquisition_category",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)
    acquisition_category: str = Field(max_length=32, nullable=False, index=True)
    acquisition_priority: str = Field(max_length=16, nullable=False, index=True)
    recommendation_strength: str = Field(max_length=16, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
