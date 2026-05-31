from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarketplaceCapabilityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    marketplace_id: int
    capability_code: str
    capability_name: str


class MarketplaceDefinitionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    marketplace_code: str
    marketplace_name: str
    description: str | None = None
    enabled: bool
    capabilities: list[MarketplaceCapabilityRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MarketplaceAccountRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    marketplace_id: int
    owner_id: int
    account_name: str
    account_identifier: str
    status: str
    marketplace: MarketplaceDefinitionRead | None = None
    created_at: datetime
    updated_at: datetime


class MarketplaceAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_id: int = Field(gt=0)
    account_name: str = Field(min_length=1, max_length=160)
    account_identifier: str = Field(min_length=1, max_length=160)
    status: str = Field(default="PENDING", min_length=3, max_length=24)
    credential_type: str | None = Field(default=None, min_length=2, max_length=40)
    credential_payload: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_credential_pair(self) -> "MarketplaceAccountCreate":
        if (self.credential_type is None) != (self.credential_payload is None):
            raise ValueError("credential_type and credential_payload must be provided together.")
        return self


class MarketplaceExecutionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    marketplace_id: int
    account_id: int | None = None
    execution_uuid: str
    execution_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime


class MarketplaceExecutionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution: MarketplaceExecutionRead
    marketplace: MarketplaceDefinitionRead
    account: MarketplaceAccountRead | None = None


class MarketplaceDefinitionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceDefinitionRead]
    total_items: int
    limit: int
    offset: int


class MarketplaceAccountListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceAccountRead]
    total_items: int
    limit: int
    offset: int


class MarketplaceExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceExecutionRead]
    total_items: int
    limit: int
    offset: int
