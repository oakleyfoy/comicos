from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON, String, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_job_uuid() -> str:
    return str(uuid4())


class MarketplacePublishJob(SQLModel, table=True):
    __tablename__ = "marketplace_publish_job"
    __table_args__ = (
        UniqueConstraint("job_uuid", name="uq_marketplace_publish_job_uuid"),
        SAIndex("ix_marketplace_publish_job_job_uuid", "job_uuid"),
        SAIndex("ix_marketplace_publish_job_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", nullable=False, index=True)
    job_uuid: str = Field(default_factory=generate_job_uuid, max_length=64, nullable=False)
    status: str = Field(max_length=24, nullable=False, index=True)
    requested_by: int = Field(foreign_key="user.id", nullable=False, index=True)
    requested_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplacePublishTarget(SQLModel, table=True):
    __tablename__ = "marketplace_publish_target"
    __table_args__ = (
        SAIndex("ix_marketplace_publish_target_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    publish_job_id: int = Field(foreign_key="marketplace_publish_job.id", nullable=False, index=True)
    marketplace_id: int = Field(foreign_key="marketplace_definition.id", nullable=False, index=True)
    marketplace_account_id: int | None = Field(default=None, foreign_key="marketplace_account.id", nullable=True, index=True)
    listing_mapping_id: int | None = Field(default=None, foreign_key="marketplace_listing_mapping.id", nullable=True, index=True)
    target_status: str = Field(max_length=24, nullable=False, index=True)
    planned_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_payload_json: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplacePublishEvent(SQLModel, table=True):
    __tablename__ = "marketplace_publish_event"
    __table_args__ = (
        SAIndex("ix_marketplace_publish_event_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    publish_job_id: int = Field(foreign_key="marketplace_publish_job.id", nullable=False, index=True)
    event_type: str = Field(max_length=80, nullable=False)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MarketplacePublishValidationIssue(SQLModel, table=True):
    __tablename__ = "marketplace_publish_validation_issue"
    __table_args__ = (
        SAIndex("ix_marketplace_publish_validation_issue_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    publish_job_id: int = Field(foreign_key="marketplace_publish_job.id", nullable=False, index=True)
    issue_code: str = Field(max_length=80, nullable=False)
    issue_message: str = Field(sa_column=Column(String, nullable=False))
    severity: str = Field(max_length=24, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
