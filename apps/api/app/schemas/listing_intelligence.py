"""P36-06 schemas for deterministic listing intelligence."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ListingIntelligenceStatus = Literal["STRONG", "ADEQUATE", "WEAK", "INCOMPLETE", "INSUFFICIENT_DATA"]
ListingCompletenessStatus = Literal["PASS", "WARNING", "FAIL"]
ListingCompletenessSeverity = Literal["info", "warning", "critical"]
ListingIntelligenceEvidenceType = Literal["LISTING_FIELD", "IMAGE", "PRICE", "EXPORT_RUN", "SALE", "LIQUIDITY", "CONVENTION"]
ListingIntelligenceCheckKey = Literal[
    "title_present",
    "description_present",
    "condition_present",
    "price_present",
    "currency_present",
    "image_present",
    "primary_image_present",
    "inventory_link_present",
    "exportable_status",
]


class ListingIntelligenceGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: date | None = None
    listing_id: int | None = Field(default=None, ge=1)
    inventory_item_id: int | None = Field(default=None, ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    channel: str | None = Field(default=None, min_length=2, max_length=40)
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ListingIntelligenceSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    listing_id: int
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    channel: str | None
    replay_key: str | None
    intelligence_status: ListingIntelligenceStatus | str
    completeness_score: Decimal
    image_score: Decimal
    title_score: Decimal
    description_score: Decimal
    pricing_score: Decimal
    export_readiness_score: Decimal
    sale_outcome_score: Decimal | None
    stale_risk_flag: bool
    missing_required_fields_json: list
    warning_flags_json: list
    evidence_count: int
    checksum: str
    snapshot_date: date
    created_at: datetime


class ListingIntelligenceEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    intelligence_snapshot_id: int
    evidence_type: ListingIntelligenceEvidenceType | str
    source_listing_id: int | None
    source_export_run_id: int | None
    source_sale_id: int | None
    source_liquidity_snapshot_id: int | None
    source_convention_event_id: int | None
    evidence_key: str
    evidence_value_json: dict
    created_at: datetime


class ListingCompletenessCheckRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    intelligence_snapshot_id: int
    owner_user_id: int
    listing_id: int
    replay_key: str | None
    status: ListingCompletenessStatus | str
    check_key: ListingIntelligenceCheckKey | str
    message: str
    severity: ListingCompletenessSeverity | str
    snapshot_date: date
    created_at: datetime


class ListingChannelPerformanceSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    channel: str
    replay_key: str | None
    total_listings: int
    active_listings: int
    sold_listings: int
    cancelled_listings: int
    exported_count: int
    sales_count: int
    gross_sales_amount: Decimal
    net_proceeds_amount: Decimal
    median_days_to_sale: Decimal | None
    stale_listing_count: int
    checksum: str
    snapshot_date: date
    created_at: datetime


class ListingIntelligenceDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strong_listing_count: int
    incomplete_listing_count: int
    average_completeness_score: Decimal | None
    export_ready_count: int
    stale_risk_count: int
    recent_weak_or_incomplete: list[ListingIntelligenceSnapshotRead]


class ListingIntelligenceGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_snapshot_count: int
    generated_evidence_count: int
    generated_check_count: int
    generated_channel_performance_count: int
    checksum: str
    snapshot_date: date
    replay_key: str | None


class ListingIntelligenceSnapshotListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ListingIntelligenceSnapshotRead]
    total_items: int
    limit: int
    offset: int


class ListingIntelligenceEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ListingIntelligenceEvidenceRead]
    total_items: int
    limit: int
    offset: int


class ListingCompletenessCheckListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ListingCompletenessCheckRead]
    total_items: int
    limit: int
    offset: int


class ListingChannelPerformanceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ListingChannelPerformanceSnapshotRead]
    total_items: int
    limit: int
    offset: int
