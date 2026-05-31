from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index as SAIndex, JSON, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid4())


class DataIntegrityCheck(SQLModel, table=True):
    __tablename__ = "data_integrity_check"
    __table_args__ = (
        UniqueConstraint("check_uuid", name="uq_data_integrity_check_uuid"),
        SAIndex("ix_data_integrity_check_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    check_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    check_type: str = Field(max_length=80, nullable=False, index=True)
    check_status: str = Field(max_length=24, nullable=False, index=True)
    checked_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    summary_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class DataIntegrityIssue(SQLModel, table=True):
    __tablename__ = "data_integrity_issue"
    __table_args__ = (
        SAIndex("ix_data_integrity_issue_check_created", "check_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    check_id: int = Field(foreign_key="data_integrity_check.id", nullable=False, index=True)
    issue_type: str = Field(max_length=80, nullable=False, index=True)
    severity: str = Field(max_length=24, nullable=False, index=True)
    entity_type: str = Field(max_length=80, nullable=False, index=True)
    entity_id: int | None = Field(default=None, nullable=True, index=True)
    issue_message: str = Field(sa_column=Column(Text, nullable=False))
    issue_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class MigrationSafetyCheck(SQLModel, table=True):
    __tablename__ = "migration_safety_check"
    __table_args__ = (
        SAIndex("ix_migration_safety_check_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    migration_revision: str = Field(max_length=80, nullable=False, index=True)
    check_status: str = Field(max_length=24, nullable=False, index=True)
    pre_count_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    post_count_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    validation_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    checked_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AuditEvent(SQLModel, table=True):
    __tablename__ = "audit_event"
    __table_args__ = (
        UniqueConstraint("audit_uuid", name="uq_audit_event_uuid"),
        SAIndex("ix_audit_event_owner_created", "owner_user_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    audit_uuid: str = Field(default_factory=generate_uuid, max_length=64, nullable=False, index=True)
    actor_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    actor_type: str = Field(max_length=80, nullable=False, index=True)
    action_type: str = Field(max_length=80, nullable=False, index=True)
    entity_type: str = Field(max_length=80, nullable=False, index=True)
    entity_id: int | None = Field(default=None, nullable=True, index=True)
    source: str = Field(max_length=120, nullable=False)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class ChangeRecord(SQLModel, table=True):
    __tablename__ = "change_record"
    __table_args__ = (
        SAIndex("ix_change_record_audit_created", "audit_event_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    audit_event_id: int = Field(sa_column=Column(ForeignKey("audit_event.id"), nullable=False, index=True))
    field_name: str = Field(max_length=255, nullable=False, index=True)
    before_value_json: object | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    after_value_json: object | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
