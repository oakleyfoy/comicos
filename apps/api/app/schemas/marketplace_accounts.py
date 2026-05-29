from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceAccountConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_type: str = Field(min_length=2, max_length=32)
    marketplace_account_id: str = Field(min_length=2, max_length=128)
    display_name: str = Field(min_length=2, max_length=200)
    credential_type: str = Field(default="oauth_token", min_length=2, max_length=32)
    credential_reference: str = Field(min_length=3, max_length=255)


class MarketplaceAccountDisconnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)


class MarketplaceAccountVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int = Field(gt=0)
    verification_status: str = Field(default="verified", min_length=4, max_length=24)
    reason: str | None = Field(default=None, max_length=500)


class MarketplaceRegistryEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_key: str
    display_name: str
    status: str
    capability_flags: list[str] = Field(default_factory=list)


class MarketplacePermissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_view: bool
    can_manage: bool
    role_keys: list[str] = Field(default_factory=list)
    permission_keys: list[str] = Field(default_factory=list)


class MarketplaceCredentialResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    marketplace_account_id: int
    credential_type: str
    credential_reference: str
    credential_status: str
    rotated_at: datetime | None = None
    created_at: datetime


class MarketplaceConnectionEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_account_id: int | None = None
    actor_user_id: int | None = None
    event_type: str
    event_payload_json: dict = Field(default_factory=dict)
    created_at: datetime


class MarketplaceAccountResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    organization_id: int
    marketplace_type: str
    marketplace_account_id: str
    display_name: str
    account_status: str
    verification_status: str
    connected_at: datetime
    disconnected_at: datetime | None = None
    created_at: datetime


class MarketplaceAccountDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: MarketplaceAccountResponse
    credentials: list[MarketplaceCredentialResponse] = Field(default_factory=list)
    connection_events: list[MarketplaceConnectionEventResponse] = Field(default_factory=list)
    registry_entry: MarketplaceRegistryEntryResponse
    permissions: MarketplacePermissionResponse


class MarketplaceAccountListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceAccountResponse]
    registry: list[MarketplaceRegistryEntryResponse]
    permissions: MarketplacePermissionResponse
    total_items: int
    limit: int
    offset: int
