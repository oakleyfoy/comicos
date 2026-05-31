from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PULL_LIST_STATUSES = ("ACTIVE", "PAUSED", "COMPLETED", "DROPPED")
PULL_LIST_ISSUE_ACTION_STATES = ("UPCOMING", "FOC_APPROACHING", "RELEASED", "MISSED")


class PullList(SQLModel, table=True):
    __tablename__ = "pull_list"
    __table_args__ = (
        SAIndex("ix_pull_list_owner_status", "owner_user_id", "status", "id"),
        SAIndex("ix_pull_list_owner_publisher", "owner_user_id", "publisher", "id"),
        SAIndex("ix_pull_list_owner_series", "owner_user_id", "series_name", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    publisher: str = Field(max_length=120, nullable=False, index=True)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    canonical_series_id: int | None = Field(default=None, nullable=True, index=True)
    status: str = Field(default="ACTIVE", max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PullListIssue(SQLModel, table=True):
    __tablename__ = "pull_list_issue"
    __table_args__ = (
        UniqueConstraint("pull_list_id", "release_id", name="uq_pull_list_issue_release"),
        SAIndex("ix_pull_list_issue_list_release_date", "pull_list_id", "release_date", "id"),
        SAIndex("ix_pull_list_issue_list_foc_date", "pull_list_id", "foc_date", "id"),
        SAIndex("ix_pull_list_issue_list_action", "pull_list_id", "action_state", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    pull_list_id: int = Field(foreign_key="pull_list.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    issue_number: str = Field(max_length=24, nullable=False)
    title: str = Field(default="", sa_column=Column(Text, nullable=False))
    release_date: date | None = Field(default=None, nullable=True, index=True)
    foc_date: date | None = Field(default=None, nullable=True, index=True)
    action_state: str = Field(default="UPCOMING", max_length=32, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


PULL_LIST_DECISION_TYPES = ("START_RUN", "CONTINUE_RUN", "WATCH", "PASS")


class PullListDecision(SQLModel, table=True):
    __tablename__ = "pull_list_decision"
    __table_args__ = (
        SAIndex("ix_pull_list_decision_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_pull_list_decision_owner_release", "owner_user_id", "release_id", "id"),
        SAIndex("ix_pull_list_decision_owner_type", "owner_user_id", "decision_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    decision_type: str = Field(max_length=32, nullable=False, index=True)
    confidence_score: float = Field(nullable=False)
    explanation: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False, index=True))


PULL_LIST_AUTOMATION_STATUSES = ("SUCCESS", "FAILED", "PARTIAL")


class PullListAutomationSchedule(SQLModel, table=True):
    __tablename__ = "pull_list_automation_schedule"
    __table_args__ = (SAIndex("ix_pull_list_automation_schedule_next_run", "next_run_at", "enabled", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    enabled: bool = Field(default=True, nullable=False)
    schedule_time: str = Field(default="06:15", max_length=8, nullable=False)
    timezone: str = Field(default="America/Chicago", max_length=64, nullable=False)
    next_run_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PullListAutomationRun(SQLModel, table=True):
    __tablename__ = "pull_list_automation_run"
    __table_args__ = (
        SAIndex("ix_pull_list_automation_run_started", "started_at", "id"),
        SAIndex("ix_pull_list_automation_run_status", "status", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="SUCCESS", max_length=16, nullable=False)
    owners_processed: int = Field(default=0, nullable=False)
    releases_processed: int = Field(default=0, nullable=False)
    decisions_created: int = Field(default=0, nullable=False)
    actions_generated: int = Field(default=0, nullable=False)
    runtime_ms: int = Field(default=0, nullable=False)
    error_message: str = Field(default="", sa_column=Column(Text, nullable=False))


PULL_LIST_CERTIFICATION_RESULTS = ("NOT_READY", "READY_WITH_WARNINGS", "APPROVED_FOR_PRODUCTION")


class PullListCertificationRun(SQLModel, table=True):
    __tablename__ = "pull_list_certification_run"
    __table_args__ = (
        SAIndex("ix_pull_list_certification_run_started", "started_at", "id"),
        SAIndex("ix_pull_list_certification_run_result", "certification_result", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    started_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="SUCCESS", max_length=16, nullable=False)
    readiness_score: float = Field(default=0.0, nullable=False)
    foundation_score: float = Field(default=0.0, nullable=False)
    decision_engine_score: float = Field(default=0.0, nullable=False)
    dashboard_score: float = Field(default=0.0, nullable=False)
    automation_score: float = Field(default=0.0, nullable=False)
    determinism_score: float = Field(default=0.0, nullable=False)
    operations_score: float = Field(default=0.0, nullable=False)
    certification_result: str = Field(default="NOT_READY", max_length=32, nullable=False)
    validation_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
