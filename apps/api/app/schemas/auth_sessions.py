from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserAuthSessionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    device_label: str
    device_type: str
    ip_address: str | None = None
    user_agent: str | None = None
    organization_id: int | None = None
    session_status: str
    issued_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    is_current: bool = False


class UserAuthSessionEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    auth_session_id: int | None = None
    user_id: int | None = None
    organization_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class OrganizationSecurityContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    user_id: int
    active_organization_id: int | None = None
    active_organization_slug: str | None = None
    active_organization_display_name: str | None = None
    last_org_switch_at: datetime | None = None
    session_id: int
    session_status: str
    session_expires_at: datetime
    role_keys: list[str] = Field(default_factory=list)
    permission_keys: list[str] = Field(default_factory=list)


class UserAuthSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[UserAuthSessionRead]
    total_items: int
    limit: int
    offset: int


class RevokeAuthSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int = Field(ge=1)


class SwitchOrganizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int = Field(ge=1)
