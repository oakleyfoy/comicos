from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MarketplacePublishRequestTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_id: int = Field(gt=0)
    marketplace_account_id: int | None = Field(default=None, gt=0)


class MarketplacePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int = Field(gt=0)
    targets: list[MarketplacePublishRequestTarget] = Field(min_length=1)


class MarketplacePublishTargetRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    publish_job_id: int
    marketplace_id: int
    marketplace_account_id: int | None = None
    listing_mapping_id: int | None = None
    target_status: str
    planned_payload_json: dict[str, Any] = Field(default_factory=dict)
    result_payload_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class MarketplacePublishEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    publish_job_id: int
    event_type: str
    event_payload_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MarketplacePublishValidationIssueRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    publish_job_id: int
    issue_code: str
    issue_message: str
    severity: str
    created_at: datetime


class MarketplacePublishJobRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_id: int
    listing_id: int
    job_uuid: str
    status: str
    requested_by: int
    requested_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime


class MarketplacePublishJobDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job: MarketplacePublishJobRead
    targets: list[MarketplacePublishTargetRead] = Field(default_factory=list)
    events: list[MarketplacePublishEventRead] = Field(default_factory=list)
    validation_issues: list[MarketplacePublishValidationIssueRead] = Field(default_factory=list)


class MarketplacePublishJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplacePublishJobRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int
