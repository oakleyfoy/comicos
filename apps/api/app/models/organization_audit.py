from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrganizationAuditLedger(SQLModel, table=True):
    __tablename__ = "organization_audit_ledger"
    __table_args__ = (
        SAIndex("ix_org_audit_ledger_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_org_audit_ledger_org_category_created", "organization_id", "audit_category", "created_at", "id"),
        SAIndex("ix_org_audit_ledger_org_resource_created", "organization_id", "resource_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    audit_category: str = Field(max_length=32, nullable=False, index=True)
    audit_action: str = Field(max_length=64, nullable=False, index=True)
    resource_type: str = Field(max_length=64, nullable=False, index=True)
    resource_id: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    audit_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationComplianceEvent(SQLModel, table=True):
    __tablename__ = "organization_compliance_events"
    __table_args__ = (
        SAIndex("ix_org_compliance_event_org_created", "organization_id", "created_at", "id"),
        SAIndex("ix_org_compliance_event_org_severity_created", "organization_id", "severity_level", "created_at", "id"),
        SAIndex("ix_org_compliance_event_org_type_created", "organization_id", "compliance_event_type", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    compliance_event_type: str = Field(max_length=80, nullable=False, index=True)
    severity_level: str = Field(max_length=16, nullable=False, index=True)
    event_payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class OrganizationAuditAccessLog(SQLModel, table=True):
    __tablename__ = "organization_audit_access_logs"
    __table_args__ = (
        SAIndex("ix_org_audit_access_log_org_created", "organization_id", "created_at", "id"),
        SAIndex(
            "ix_org_audit_access_log_org_resource_created",
            "organization_id",
            "accessed_resource_type",
            "created_at",
            "id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organizations.id", nullable=False, index=True)
    actor_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    accessed_resource_type: str = Field(max_length=64, nullable=False, index=True)
    accessed_resource_id: str | None = Field(default=None, max_length=128, nullable=True, index=True)
    access_result: str = Field(max_length=24, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
