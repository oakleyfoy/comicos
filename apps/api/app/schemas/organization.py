from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=120)
    organization_type: str = Field(default="DEALER", min_length=3, max_length=24)


class OrganizationInviteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    expires_in_days: int = Field(default=7, ge=1, le=30)


class OrganizationArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    public_id: str
    owner_user_id: int
    display_name: str
    slug: str
    organization_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None
    active_member_count: int = 0
    pending_invitation_count: int = 0
    current_user_role_keys: list[str] = Field(default_factory=list)
    current_user_permission_keys: list[str] = Field(default_factory=list)


class OrganizationMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    user_id: int
    user_email: str
    membership_status: str
    joined_at: datetime
    invited_by_user_id: int | None = None
    removed_at: datetime | None = None
    is_owner: bool = False
    role_keys: list[str] = Field(default_factory=list)
    effective_permission_keys: list[str] = Field(default_factory=list)


class OrganizationInvitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    email: str
    invitation_token: str
    status: str
    expires_at: datetime
    accepted_at: datetime | None = None
    invited_by_user_id: int
    created_at: datetime


class OrganizationEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class OrganizationRoleAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_key: str = Field(min_length=2, max_length=32)


class OrganizationRoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    role_key: str
    display_name: str
    system_managed: bool
    created_at: datetime
    permission_keys: list[str] = Field(default_factory=list)


class OrganizationMembershipRoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_member_id: int
    organization_role_id: int
    role_key: str
    display_name: str
    assigned_by_user_id: int
    assigned_at: datetime
    permission_keys: list[str] = Field(default_factory=list)


class OrganizationPermissionAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    actor_user_id: int | None = None
    target_user_id: int | None = None
    action_key: str
    permission_result: str
    evaluation_context_json: dict
    created_at: datetime


class OrganizationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationMemberListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationMemberResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationEventResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationRoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationRoleResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationMembershipRoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationMembershipRoleResponse]
    total_items: int
    limit: int
    offset: int


class OrganizationPermissionAuditListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OrganizationPermissionAuditResponse]
    total_items: int
    limit: int
    offset: int
