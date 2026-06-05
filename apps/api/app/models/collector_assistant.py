"""P64 Collector Assistant models (Phase A)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel

P64_COLLECTOR_ASSISTANT_SOURCE_VERSION = "P64-A"

RUN_STATUS_SUCCESS = "SUCCESS"
RUN_STATUS_NOT_READY = "NOT_READY"
RUN_STATUS_FAILED = "FAILED"

LANE_BUY = "BUY"
LANE_HOLD = "HOLD"
LANE_SELL = "SELL"
LANE_GRADE = "GRADE"
LANE_ACQUIRE = "ACQUIRE"
LANE_WATCH = "WATCH"

COLLECTOR_LANES = (LANE_BUY, LANE_HOLD, LANE_SELL, LANE_GRADE, LANE_ACQUIRE, LANE_WATCH)

ITEM_STATUS_NEW = "NEW"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CollectorAssistantRun(SQLModel, table=True):
    __tablename__ = "collector_assistant_run"
    __table_args__ = (SAIndex("ix_collector_assistant_run_owner_started", "owner_user_id", "started_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default=RUN_STATUS_SUCCESS, max_length=16, nullable=False, index=True)
    upstream_fingerprint_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    steps_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source_version: str = Field(default=P64_COLLECTOR_ASSISTANT_SOURCE_VERSION, max_length=32, nullable=False)


class CollectorBriefingSnapshot(SQLModel, table=True):
    __tablename__ = "collector_briefing_snapshot"
    __table_args__ = (SAIndex("ix_collector_briefing_run", "run_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collector_assistant_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    week_start: date = Field(sa_column=Column(Date, nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    readiness_status: str = Field(default=RUN_STATUS_SUCCESS, max_length=16, nullable=False)
    briefing_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    briefing_markdown: str = Field(default="", sa_column=Column(Text, nullable=False))
    source_versions_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class CollectorRecommendationSnapshot(SQLModel, table=True):
    __tablename__ = "collector_recommendation_snapshot"
    __table_args__ = (SAIndex("ix_collector_rec_snap_run_lane", "run_id", "lane", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collector_assistant_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    lane: str = Field(max_length=16, nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    total_items: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class CollectorRecommendationItem(SQLModel, table=True):
    __tablename__ = "collector_recommendation_item"
    __table_args__ = (SAIndex("ix_collector_rec_item_snap_pri", "snapshot_id", "priority_score", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(foreign_key="collector_recommendation_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    lane: str = Field(max_length=16, nullable=False, index=True)
    priority_score: float = Field(default=0.0, nullable=False, index=True)
    confidence: str = Field(default="MEDIUM", max_length=16, nullable=False)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    publisher: str = Field(default="", max_length=120, nullable=False)
    issue_number: str = Field(default="", max_length=32, nullable=False)
    release_issue_id: int | None = Field(default=None, foreign_key="release_issue.id", nullable=True)
    external_catalog_issue_id: int | None = Field(default=None, foreign_key="external_catalog_issue.id", nullable=True)
    inventory_copy_id: int | None = Field(default=None, foreign_key="inventory_copy.id", nullable=True)
    recommended_action: str = Field(default="", max_length=32, nullable=False)
    reason_codes_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    explanation: str = Field(default="", sa_column=Column(Text, nullable=False))
    provenance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default=ITEM_STATUS_NEW, max_length=16, nullable=False, index=True)


class CollectorHealthSnapshot(SQLModel, table=True):
    __tablename__ = "collector_health_snapshot"
    __table_args__ = (SAIndex("ix_collector_health_run", "run_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collector_assistant_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    readiness_status: str = Field(default=RUN_STATUS_SUCCESS, max_length=16, nullable=False)
    health_score: float = Field(default=0.0, nullable=False)
    health_band: str = Field(default="FAIR", max_length=16, nullable=False)
    metrics_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    risk_flags_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))


class CollectorOpportunityAlertSnapshot(SQLModel, table=True):
    __tablename__ = "collector_opportunity_alert_snapshot"
    __table_args__ = (SAIndex("ix_collector_alert_snap_run", "run_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collector_assistant_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    alert_count: int = Field(default=0, nullable=False)
    critical_count: int = Field(default=0, nullable=False)
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class CollectorOpportunityAlert(SQLModel, table=True):
    __tablename__ = "collector_opportunity_alert"
    __table_args__ = (SAIndex("ix_collector_alert_snap_sev", "alert_snapshot_id", "severity", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    alert_snapshot_id: int = Field(foreign_key="collector_opportunity_alert_snapshot.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    alert_type: str = Field(max_length=32, nullable=False, index=True)
    severity: str = Field(max_length=16, nullable=False, index=True)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    action_deep_link: str = Field(default="", max_length=256, nullable=False)
    provenance_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class CollectorExecutiveBundle(SQLModel, table=True):
    __tablename__ = "collector_executive_bundle"
    __table_args__ = (SAIndex("ix_collector_executive_run", "run_id", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="collector_assistant_run.id", nullable=False, index=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    readiness_status: str = Field(default=RUN_STATUS_SUCCESS, max_length=16, nullable=False)
    platform_ready: bool = Field(default=False, nullable=False)
    dashboard_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    freshness_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
