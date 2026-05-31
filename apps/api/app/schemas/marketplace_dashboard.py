from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketplaceValidationCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_code: str
    title: str
    status: str
    summary: str
    details_json: dict[str, object]


class MarketplaceValidationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    platform_certified: bool
    checks: list[MarketplaceValidationCheckRead]


class MarketplaceHealthComponentRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_code: str
    title: str
    health_status: str
    summary: str
    details_json: dict[str, object] = Field(default_factory=dict)


class MarketplaceHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_status: str
    components: list[MarketplaceHealthComponentRead]


class MarketplaceAnalyticsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listings_by_status: dict[str, int]
    publish_jobs_by_status: dict[str, int]
    orders_by_status: dict[str, int]
    reservations_by_status: dict[str, int]
    sync_plans_by_status: dict[str, int]
    marketplace_activity_counts: dict[str, int]
    generated_at: str


class MarketplaceConnectorReadinessRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marketplace_id: int
    marketplace_code: str
    marketplace_name: str
    enabled: bool
    implementation_ready: bool
    capability_count: int
    health_status: str
    summary: str


class MarketplaceConnectorReadinessListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceConnectorReadinessRead]
    total_items: int


class MarketplaceAccountHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int
    marketplace_id: int
    marketplace_code: str
    account_name: str
    status: str
    health_status: str
    credentials_present: bool
    summary: str


class MarketplaceAccountHealthListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketplaceAccountHealthRead]
    total_items: int


class MarketplaceDashboardSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validation_status: str
    health_status: str
    platform_certified: bool
    summary_cards: dict[str, int]
    validation_checks: list[MarketplaceValidationCheckRead]
    health_components: list[MarketplaceHealthComponentRead]
