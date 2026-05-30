from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentPermissionPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: int = Field(ge=1)
    capability_code: str = Field(min_length=1, max_length=120)
    permission_scope: str = Field(min_length=1, max_length=24)
    allowed: bool


class AgentPermissionPolicyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    agent_id: int
    capability_code: str
    permission_scope: str
    allowed: bool
    created_at: datetime
    updated_at: datetime


class AgentPermissionAuditEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    agent_id: int
    execution_id: int | None
    capability_code: str
    action_code: str
    decision: str
    reason: str
    event_payload_json: dict[str, Any]
    created_at: datetime


class AgentPermissionCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: int = Field(ge=1)
    capability_code: str = Field(min_length=1, max_length=120)
    permission_scope: str = Field(min_length=1, max_length=24)
    action_code: str = Field(min_length=1, max_length=120)
    execution_id: int | None = Field(default=None, ge=1)
    event_payload_json: dict[str, Any] = Field(default_factory=dict)


class AgentPermissionCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: int
    execution_id: int | None
    capability_code: str
    permission_scope: str
    action_code: str
    allowed: bool
    decision: str
    reason: str


class AgentPermissionPolicyDeleteRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: int
    deleted: bool


class AgentPermissionPolicyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentPermissionPolicyRead]
    total_items: int
    limit: int
    offset: int


class AgentPermissionAuditEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentPermissionAuditEventRead]
    total_items: int
    limit: int
    offset: int
