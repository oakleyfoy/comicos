from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MobileDeviceSecurityPermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool


class MobileDeviceTrustStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    mobile_device_id: int
    trust_status: str
    trust_reason: str | None
    trusted_at: datetime | None
    suspended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MobileDeviceSecurityPolicyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    policy_key: str
    policy_status: str
    policy_payload_json: dict
    created_at: datetime
    updated_at: datetime


class MobileDeviceAccessLogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    mobile_device_id: int
    user_id: int
    access_result: str
    access_reason: str
    accessed_at: datetime


class MobileDeviceSecurityEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    mobile_device_id: int | None
    actor_user_id: int | None
    event_type: str
    event_payload_json: dict
    created_at: datetime


class MobileDeviceSecurityDiagnosticResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostic_code: str
    diagnostic_status: str
    diagnostic_message: str
    diagnostic_payload_json: dict


class MobileDeviceTrustStateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobile_device_id: int
    trust_status: str = Field(min_length=1, max_length=24)
    trust_reason: str | None = Field(default=None, max_length=255)


class MobileDeviceTrustStateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trust_status: str = Field(min_length=1, max_length=24)
    trust_reason: str | None = Field(default=None, max_length=255)


class MobileDeviceSecurityPolicyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_key: str = Field(min_length=1, max_length=64)
    policy_status: str = Field(min_length=1, max_length=16)
    policy_payload_json: dict = Field(default_factory=dict)


class MobileDeviceSecurityPolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_status: str = Field(min_length=1, max_length=16)
    policy_payload_json: dict = Field(default_factory=dict)


class MobileDeviceTrustStateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileDeviceSecurityPermissionResponse
    items: list[MobileDeviceTrustStateResponse]
    total_items: int
    limit: int
    offset: int


class MobileDeviceSecurityPolicyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileDeviceSecurityPermissionResponse
    items: list[MobileDeviceSecurityPolicyResponse]
    total_items: int
    limit: int
    offset: int


class MobileDeviceAccessLogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileDeviceSecurityPermissionResponse
    items: list[MobileDeviceAccessLogResponse]
    total_items: int
    limit: int
    offset: int


class MobileDeviceSecurityEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileDeviceSecurityPermissionResponse
    items: list[MobileDeviceSecurityEventResponse]
    total_items: int
    limit: int
    offset: int


class MobileDeviceSecurityDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: int
    permissions: MobileDeviceSecurityPermissionResponse
    summary: dict
    diagnostics: list[MobileDeviceSecurityDiagnosticResponse]
    trust_states: list[MobileDeviceTrustStateResponse]
    policies: list[MobileDeviceSecurityPolicyResponse]
    access_logs: list[MobileDeviceAccessLogResponse]
    events: list[MobileDeviceSecurityEventResponse]
