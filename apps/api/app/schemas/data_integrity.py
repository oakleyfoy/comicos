from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DataIntegrityIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_id: int
    issue_type: str
    severity: str
    entity_type: str
    entity_id: int | None = None
    issue_message: str
    issue_payload_json: dict[str, object]
    created_at: datetime


class DataIntegrityCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    check_uuid: str
    check_type: str
    check_status: str
    checked_at: datetime
    summary_json: dict[str, object]
    created_at: datetime


class DataIntegrityCheckDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: DataIntegrityCheckRead
    issues: list[DataIntegrityIssueRead] = Field(default_factory=list)


class MigrationSafetyCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    migration_revision: str
    check_status: str
    pre_count_json: dict[str, object]
    post_count_json: dict[str, object]
    validation_payload_json: dict[str, object]
    checked_at: datetime
    created_at: datetime


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    audit_uuid: str
    actor_id: int | None = None
    actor_type: str
    action_type: str
    entity_type: str
    entity_id: int | None = None
    source: str
    event_payload_json: dict[str, object]
    created_at: datetime


class ChangeRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    audit_event_id: int
    field_name: str
    before_value_json: object | None = None
    after_value_json: object | None = None
    created_at: datetime


class AuditEventDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: AuditEventRead
    changes: list[ChangeRecordRead] = Field(default_factory=list)


class DataIntegrityCheckListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DataIntegrityCheckRead]
    total_items: int
    limit: int
    offset: int


class DataIntegrityIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DataIntegrityIssueRead]
    total_items: int
    limit: int
    offset: int


class MigrationSafetyCheckListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MigrationSafetyCheckRead]
    total_items: int
    limit: int
    offset: int


class AuditEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEventRead]
    total_items: int
    limit: int
    offset: int


class MigrationSafetyValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    migration_revision: str
    pre_count_json: dict[str, int] = Field(default_factory=dict)
    post_count_json: dict[str, int] = Field(default_factory=dict)

