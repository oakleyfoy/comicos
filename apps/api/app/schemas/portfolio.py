"""P38-01 portfolio registry & exposure payloads."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

PortfolioTypeLiteral = Literal[
    "personal_collection",
    "dealer_inventory",
    "investment_portfolio",
    "grading_pipeline",
    "convention_inventory",
    "watchlist",
]

PortfolioStatusLiteral = Literal["ACTIVE", "ARCHIVED"]

AllocationRoleLiteral = Literal[
    "core_holding",
    "duplicate",
    "grading_candidate",
    "sale_candidate",
    "convention_stock",
    "speculative",
    "watchlist",
]

AllocatedValueSourceLiteral = Literal[
    "current_fmv",
    "acquisition_cost",
    "manual",
    "graded_estimate",
]

ExposureTypeLiteral = Literal[
    "publisher",
    "title",
    "character",
    "creator",
    "era",
    "grade_status",
    "liquidity_status",
    "value_band",
    "acquisition_source",
]

ExposureStatusLiteral = Literal[
    "BALANCED",
    "WATCH",
    "CONCENTRATED",
    "OVEREXPOSED",
    "INSUFFICIENT_DATA",
]

EvidenceTypeLiteral = Literal[
    "INVENTORY",
    "FMV",
    "SALES_LEDGER",
    "LIQUIDITY",
    "GRADING",
    "LISTING",
    "CONVENTION",
]

PortfolioLifecycleEventLiteral = Literal[
    "CREATED",
    "UPDATED",
    "ITEM_ADDED",
    "ITEM_REMOVED",
    "ARCHIVED",
    "SNAPSHOT_GENERATED",
]


class PortfolioCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    portfolio_type: PortfolioTypeLiteral
    replay_key: str | None = Field(default=None, max_length=128)


class PortfolioUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    portfolio_type: PortfolioTypeLiteral | None = None


class PortfolioRead(BaseModel):
    id: int
    owner_user_id: int
    name: str
    description: str | None
    portfolio_type: str
    status: str
    replay_key: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class PortfolioListResponse(BaseModel):
    items: list[PortfolioRead]
    total_items: int
    limit: int
    offset: int


class PortfolioItemCreatePayload(BaseModel):
    inventory_item_id: int
    allocation_role: AllocationRoleLiteral
    allocated_value_amount: Decimal | None = Field(default=None, ge=Decimal("0"))
    allocated_value_source: AllocatedValueSourceLiteral | None = None


class PortfolioItemRead(BaseModel):
    id: int
    portfolio_id: int
    inventory_item_id: int
    allocation_role: str
    allocated_value_amount: Decimal | None
    allocated_value_source: str | None
    added_at: datetime
    removed_at: datetime | None
    created_at: datetime


class PortfolioItemListResponse(BaseModel):
    items: list[PortfolioItemRead]
    total_items: int
    limit: int
    offset: int


class PortfolioExposureEvidenceRead(BaseModel):
    id: int
    portfolio_exposure_snapshot_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict
    created_at: datetime


class PortfolioExposureEvidenceListResponse(BaseModel):
    items: list[PortfolioExposureEvidenceRead]
    total_items: int
    limit: int
    offset: int


class PortfolioExposureSnapshotRead(BaseModel):
    id: int
    owner_user_id: int
    portfolio_id: int | None
    generation_scope_key: str
    replay_key: str | None
    generation_batch_checksum: str
    exposure_type: str
    exposure_key: str
    item_count: int
    total_fmv_amount: Decimal | None
    total_cost_basis_amount: Decimal | None
    total_realized_sales_amount: Decimal | None
    percentage_of_portfolio_value: Decimal | None
    percentage_of_portfolio_count: Decimal | None
    exposure_status: str
    checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioExposureSnapshotListResponse(BaseModel):
    items: list[PortfolioExposureSnapshotRead]
    total_items: int
    limit: int
    offset: int


class PortfolioAllocationSnapshotRead(BaseModel):
    id: int
    owner_user_id: int
    portfolio_id: int | None
    generation_scope_key: str
    replay_key: str | None
    total_item_count: int
    total_fmv_amount: Decimal | None
    total_cost_basis_amount: Decimal | None
    total_realized_sales_amount: Decimal | None
    graded_item_count: int
    raw_item_count: int
    listed_item_count: int
    sold_item_count: int
    high_liquidity_count: int
    low_liquidity_count: int
    grading_candidate_count: int
    sale_candidate_count: int
    duplicate_count: int
    convention_assigned_count: int
    checksum: str
    snapshot_date: date
    created_at: datetime


class PortfolioAllocationSnapshotListResponse(BaseModel):
    items: list[PortfolioAllocationSnapshotRead]
    total_items: int
    limit: int
    offset: int


class PortfolioGenerateScopePayload(BaseModel):
    portfolio_id: int | None = None
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, max_length=128)


class PortfolioExposureGenerateResponse(BaseModel):
    generation_batch_checksum: str
    snapshot_date: date
    snapshots: list[PortfolioExposureSnapshotRead]
    replayed: bool


class PortfolioAllocationGenerateResponse(BaseModel):
    snapshot_date: date
    allocation: PortfolioAllocationSnapshotRead | None = None
    replayed: bool


class PortfolioIntelligenceExposureTeaser(BaseModel):
    exposure_type: str
    exposure_key: str
    exposure_status: str
    percentage_of_portfolio_value: Decimal | None


class PortfolioIntelligenceSummary(BaseModel):
    active_portfolio_count: int
    latest_allocation_scope_key: str | None = None
    latest_allocation_checksum: str | None = None
    latest_generation_batch_checksum: str | None = None
    total_item_count: int | None = None
    total_fmv_amount: Decimal | None = None
    total_cost_basis_amount: Decimal | None = None
    graded_item_count: int | None = None
    raw_item_count: int | None = None
    low_liquidity_count: int | None = None
    high_liquidity_count: int | None = None
    overexposed_rows: list[PortfolioIntelligenceExposureTeaser] = Field(default_factory=list)


class PortfolioMembershipRead(BaseModel):
    portfolio_id: int
    portfolio_name: str
    portfolio_type: str
    allocation_role: str


class InventoryPortfolioIntelligenceTeaser(BaseModel):
    memberships: list[PortfolioMembershipRead] = Field(default_factory=list)
    publisher_exposure_status: str | None = None
    publisher_exposure_pct_value: Decimal | None = None
