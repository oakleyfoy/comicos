from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AUDIT_CATEGORIES: tuple[str, ...] = (
    "organization",
    "permissions",
    "inventory",
    "reviews",
    "storefront",
    "security",
    "sessions",
    "notifications",
)

SEVERITY_LEVELS: tuple[str, ...] = (
    "info",
    "warning",
    "elevated",
    "critical",
)

AuditCategory = Literal[
    "organization",
    "permissions",
    "inventory",
    "reviews",
    "storefront",
    "security",
    "sessions",
    "notifications",
]
ComplianceSeverityLevel = Literal["info", "warning", "elevated", "critical"]

LINEAGE_COMPLIANCE_PREFIX = "lineage."


class OrganizationAuditLedgerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    audit_category: str
    audit_action: str
    resource_type: str
    resource_id: str | None = None
    audit_payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class OrganizationComplianceEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    compliance_event_type: str
    severity_level: str
    event_payload_json: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class OrganizationAuditAccessLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int
    accessed_resource_type: str
    accessed_resource_id: str | None = None
    access_result: str
    created_at: datetime


class OrganizationAuditLedgerListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationAuditLedgerResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationComplianceEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationComplianceEventResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationAuditAccessLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationAuditAccessLogResponse]
    total_items: int
    limit: int
    offset: int
