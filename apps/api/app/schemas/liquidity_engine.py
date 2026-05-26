"""P36-04 schemas for deterministic inventory liquidity analytics."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LiquidityStatus = Literal["HIGH", "MODERATE", "LOW", "ILLIQUID", "INSUFFICIENT_DATA"]
LiquidityConfidence = Literal["HIGH", "MEDIUM", "LOW"]
LiquidityEvidenceType = Literal["SALE", "ACTIVE_LISTING", "FAILED_LISTING", "RELIST", "STALE"]
ListingStalenessEventType = Literal["STALE_WARNING", "STALE_CONFIRMED", "LONG_RUNNING"]


class InventoryLiquiditySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    inventory_item_id: int | None
    canonical_comic_issue_id: int | None
    channel: str | None
    liquidity_status: LiquidityStatus
    days_on_market_median: Decimal | None
    days_to_sale_median: Decimal | None
    sell_through_rate_pct: Decimal
    stale_listing_rate_pct: Decimal
    relist_rate_pct: Decimal
    successful_sale_count: int
    failed_listing_count: int
    active_listing_count: int
    liquidity_confidence: LiquidityConfidence
    evaluation_window_days: int
    snapshot_date: date
    checksum: str
    evidence_count: int
    created_at: datetime


class InventoryLiquidityEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    liquidity_snapshot_id: int
    evidence_type: LiquidityEvidenceType
    source_listing_id: int | None
    source_sale_id: int | None
    source_export_run_id: int | None
    days_on_market: Decimal | None
    evidence_json: dict
    created_at: datetime


class ListingVelocitySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    owner_user_id: int
    first_activated_at: datetime | None
    sold_at: datetime | None
    days_active: Decimal | None
    relist_count: int
    price_change_count: int
    final_status: str
    snapshot_date: date
    created_at: datetime


class ListingStalenessEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    owner_user_id: int
    event_type: ListingStalenessEventType
    threshold_days: int
    days_active: Decimal
    created_at: datetime


class InventoryLiquidityListResponse(BaseModel):
    items: list[InventoryLiquiditySnapshotRead]
    total_items: int
    limit: int
    offset: int


class InventoryLiquidityEvidenceListResponse(BaseModel):
    items: list[InventoryLiquidityEvidenceRead]
    total_items: int
    limit: int
    offset: int


class ListingVelocityListResponse(BaseModel):
    items: list[ListingVelocitySnapshotRead]
    total_items: int
    limit: int
    offset: int


class ListingStalenessEventListResponse(BaseModel):
    items: list[ListingStalenessEventRead]
    total_items: int
    limit: int
    offset: int


class LiquidityDashboardSummary(BaseModel):
    high_liquidity_count: int
    stale_inventory_count: int
    recent_stale_events: list[ListingStalenessEventRead]
    median_days_to_sale: Decimal | None
    sell_through_pct: Decimal
    recent_snapshots: list[InventoryLiquiditySnapshotRead]
