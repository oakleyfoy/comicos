"""P38-04 deterministic portfolio hold/sell recommendation ledger."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioRecommendation(SQLModel, table=True):
    __tablename__ = "portfolio_recommendation"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "inventory_item_id",
            "snapshot_date",
            "replay_key",
            "checksum",
            name="uq_portfolio_recommendation_signature",
        ),
        SAIndex(
            "ix_portfolio_recommendation_owner_status",
            "owner_user_id",
            "recommendation_status",
            "recommendation_action",
            "id",
        ),
        SAIndex(
            "ix_portfolio_recommendation_owner_strength",
            "owner_user_id",
            "recommendation_strength",
            "confidence_level",
            "risk_level",
            "id",
        ),
        SAIndex(
            "ix_portfolio_recommendation_scope_date",
            "owner_user_id",
            "portfolio_id",
            "inventory_item_id",
            "snapshot_date",
            "id",
        ),
        SAIndex("ix_portfolio_recommendation_checksum", "checksum"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    canonical_comic_issue_id: int | None = Field(default=None, foreign_key="comic_issue.id", nullable=True, index=True)

    recommendation_action: str = Field(max_length=24, nullable=False, index=True)
    recommendation_strength: str = Field(max_length=16, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)

    estimated_liquidity_impact: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    estimated_capital_release: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    estimated_portfolio_efficiency_gain: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    expected_roi_if_graded: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))

    rationale_summary: str = Field(sa_column=Column(Text, nullable=False))
    warning_flags_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    recommendation_status: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False)
    replay_key: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioRecommendationEvidence(SQLModel, table=True):
    __tablename__ = "portfolio_recommendation_evidence"
    __table_args__ = (
        SAIndex(
            "ix_portfolio_recommendation_evidence_recommendation_created",
            "portfolio_recommendation_id",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_recommendation_id: int = Field(
        foreign_key="portfolio_recommendation.id", nullable=False, index=True
    )
    evidence_type: str = Field(max_length=32, nullable=False, index=True)
    source_id: int | None = Field(default=None, nullable=True, index=True)
    source_table: str | None = Field(default=None, max_length=80, nullable=True)
    evidence_value_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioRecommendationScenario(SQLModel, table=True):
    __tablename__ = "portfolio_recommendation_scenario"
    __table_args__ = (
        SAIndex(
            "ix_portfolio_recommendation_scenario_recommendation_name",
            "portfolio_recommendation_id",
            "scenario_name",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    portfolio_recommendation_id: int = Field(
        foreign_key="portfolio_recommendation.id", nullable=False, index=True
    )
    scenario_name: str = Field(max_length=16, nullable=False, index=True)
    projected_capital_release: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    projected_liquidity_gain: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))
    projected_portfolio_impact: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PortfolioRecommendationHistory(SQLModel, table=True):
    __tablename__ = "portfolio_recommendation_history"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "portfolio_id",
            "inventory_item_id",
            "recommendation_action",
            "recommendation_strength",
            "confidence_level",
            "risk_level",
            "snapshot_date",
            "checksum",
            name="uq_portfolio_recommendation_history_signature",
        ),
        SAIndex(
            "ix_portfolio_recommendation_history_scope_date",
            "owner_user_id",
            "portfolio_id",
            "inventory_item_id",
            "snapshot_date",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_item_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True, index=True)
    portfolio_id: int | None = Field(default=None, foreign_key="portfolio.id", nullable=True, index=True)
    recommendation_action: str = Field(max_length=24, nullable=False, index=True)
    recommendation_strength: str = Field(max_length=16, nullable=False, index=True)
    confidence_level: str = Field(max_length=16, nullable=False, index=True)
    risk_level: str = Field(max_length=16, nullable=False, index=True)
    checksum: str = Field(max_length=64, nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False, index=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
