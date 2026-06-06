"""P82–P84 combined collector expansion models."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceAcquisitionOpportunity(SQLModel, table=True):
    __tablename__ = "p82_marketplace_acquisition_opportunity"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "marketplace", "external_listing_id", name="uq_p82_mkt_acq_listing"),
        SAIndex("ix_p82_mkt_acq_owner_score", "owner_user_id", "opportunity_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    marketplace: str = Field(default="EBAY", max_length=24, nullable=False, index=True)
    external_listing_id: str = Field(max_length=128, nullable=False, index=True)
    listing_url: str = Field(default="", max_length=512, nullable=False)
    title: str = Field(default="", max_length=512, nullable=False)
    publisher: str = Field(default="", max_length=160, nullable=False)
    series: str = Field(default="", max_length=200, nullable=False)
    issue: str = Field(default="", max_length=24, nullable=False)
    variant: str = Field(default="", max_length=200, nullable=False)
    asking_price: float = Field(default=0.0, nullable=False)
    estimated_fmv: float = Field(default=0.0, nullable=False)
    discount_to_fmv: float = Field(default=0.0, nullable=False)
    liquidity: float = Field(default=0.0, nullable=False)
    velocity: float = Field(default=0.0, nullable=False)
    grading_upside: float = Field(default=0.0, nullable=False)
    ownership_status: str = Field(default="UNKNOWN", max_length=32, nullable=False)
    profile_match_score: float = Field(default=0.0, nullable=False)
    opportunity_score: float = Field(default=0.0, nullable=False, index=True)
    recommendation: str = Field(default="PASS", max_length=16, nullable=False, index=True)
    reasons_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="ACTIVE", max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplaceAcquisitionSnapshot(SQLModel, table=True):
    __tablename__ = "p82_marketplace_acquisition_snapshot"
    __table_args__ = (SAIndex("ix_p82_mkt_acq_snap_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CollectionValuationSnapshot(SQLModel, table=True):
    __tablename__ = "p83_collection_valuation_snapshot"
    __table_args__ = (SAIndex("ix_p83_valuation_snap_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    current_value: float = Field(default=0.0, nullable=False)
    forecast_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    optimization_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CollectionRiskSnapshot(SQLModel, table=True):
    __tablename__ = "p83_collection_risk_snapshot"
    __table_args__ = (SAIndex("ix_p83_risk_snap_owner_date", "owner_user_id", "snapshot_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    snapshot_date: date = Field(sa_column=Column(Date, nullable=False))
    risk_score: float = Field(default=0.0, nullable=False)
    risk_category: str = Field(default="MODERATE_RISK", max_length=24, nullable=False, index=True)
    factors_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CollectionScenarioRun(SQLModel, table=True):
    __tablename__ = "p83_collection_scenario_run"
    __table_args__ = (SAIndex("ix_p83_scenario_owner_created", "owner_user_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    scenario_type: str = Field(max_length=32, nullable=False, index=True)
    projected_value: float = Field(default=0.0, nullable=False)
    cash_generated: float = Field(default=0.0, nullable=False)
    risk_change: float = Field(default=0.0, nullable=False)
    roi_impact: float = Field(default=0.0, nullable=False)
    affected_books_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    explanation: str = Field(default="", sa_column=Column(Text, nullable=False))
    result_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class CollectorNotification(SQLModel, table=True):
    __tablename__ = "p84_collector_notification"
    __table_args__ = (SAIndex("ix_p84_notif_owner_status", "owner_user_id", "status", "priority", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    notification_type: str = Field(max_length=32, nullable=False, index=True)
    priority: str = Field(max_length=16, nullable=False, index=True)
    title: str = Field(max_length=512, nullable=False)
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    related_entity_type: str = Field(default="", max_length=32, nullable=False)
    related_entity_id: int | None = Field(default=None, nullable=True, index=True)
    action_url: str = Field(default="", max_length=512, nullable=False)
    status: str = Field(default="UNREAD", max_length=16, nullable=False, index=True)
    reasons_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    read_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    dismissed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class CollectorBriefing(SQLModel, table=True):
    __tablename__ = "p84_collector_briefing"
    __table_args__ = (SAIndex("ix_p84_briefing_owner_type_date", "owner_user_id", "briefing_type", "briefing_date", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    briefing_type: str = Field(max_length=16, nullable=False, index=True)
    briefing_date: date = Field(sa_column=Column(Date, nullable=False))
    sections_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    top_actions_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
