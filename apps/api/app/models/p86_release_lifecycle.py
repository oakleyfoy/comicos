from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, Date, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


LIFECYCLE_STAGE_EARLY_DISCOVERY = "EARLY_DISCOVERY"
LIFECYCLE_STAGE_PREORDER_ACCURACY = "PREORDER_ACCURACY"
LIFECYCLE_STAGE_RELEASE_DAY_REFRESH = "RELEASE_DAY_REFRESH"
LIFECYCLE_STAGE_POST_RELEASE_CLEANUP = "POST_RELEASE_CLEANUP"

LIFECYCLE_STAGES = (
    LIFECYCLE_STAGE_POST_RELEASE_CLEANUP,
    LIFECYCLE_STAGE_RELEASE_DAY_REFRESH,
    LIFECYCLE_STAGE_PREORDER_ACCURACY,
    LIFECYCLE_STAGE_EARLY_DISCOVERY,
)

RUN_STATUS_PENDING = "PENDING"
RUN_STATUS_RUNNING = "RUNNING"
RUN_STATUS_COMPLETE = "COMPLETE"
RUN_STATUS_COMPLETE_WITH_WARNINGS = "COMPLETE_WITH_WARNINGS"
RUN_STATUS_BLOCKED = "BLOCKED"
RUN_STATUS_FAILED = "FAILED"
RUN_STATUS_SKIPPED = "SKIPPED"


class P86ReleaseLifecycleRun(SQLModel, table=True):
    __tablename__ = "p86_release_lifecycle_run"
    __table_args__ = (
        SAIndex("ix_p86_rl_run_owner_run_date", "owner_id", "run_date", "id"),
        SAIndex("ix_p86_rl_run_owner_status", "owner_id", "status", "id"),
        SAIndex(
            "ix_p86_rl_run_owner_anchor_stage",
            "owner_id",
            "anchor_release_date",
            "lifecycle_stage",
            "run_date",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False)
    run_date: date = Field(sa_column=Column(Date, nullable=False))
    anchor_release_date: date = Field(sa_column=Column(Date, nullable=False))
    target_release_date: date = Field(sa_column=Column(Date, nullable=False))
    lifecycle_stage: str = Field(max_length=32, nullable=False)
    command: str = Field(default="", sa_column=Column(Text, nullable=False))
    status: str = Field(default=RUN_STATUS_PENDING, max_length=32, nullable=False)
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    elapsed_seconds: float | None = Field(default=None, nullable=True)
    parent_queue_count: int | None = Field(default=None, nullable=True)
    parent_captured_count: int | None = Field(default=None, nullable=True)
    issue_count: int | None = Field(default=None, nullable=True)
    variant_count: int | None = Field(default=None, nullable=True)
    warnings_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    failures_json: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    raw_path: str = Field(default="", max_length=512, nullable=False)
    crosswalk_skipped: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


REPORT_STATUS_EMPTY = "EMPTY"
REPORT_STATUS_COMPLETE = "COMPLETE"
REPORT_STATUS_COMPLETE_WITH_WARNINGS = "COMPLETE_WITH_WARNINGS"
REPORT_STATUS_NEEDS_ATTENTION = "NEEDS_ATTENTION"
REPORT_STATUS_FAILED = "FAILED"


class P86ReleaseLifecycleReport(SQLModel, table=True):
    __tablename__ = "p86_release_lifecycle_report"
    __table_args__ = (SAIndex("ix_p86_rl_report_owner_created", "owner_id", "created_at", "id"),)

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False)
    anchor_release_date: date = Field(sa_column=Column(Date, nullable=False))
    run_date: date = Field(sa_column=Column(Date, nullable=False))
    overall_status: str = Field(max_length=32, nullable=False)
    title: str = Field(max_length=256, nullable=False)
    body: str = Field(default="", sa_column=Column(Text, nullable=False))
    runs_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    action_url: str = Field(default="/release-lifecycle", max_length=512, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
