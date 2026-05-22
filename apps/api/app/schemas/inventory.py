from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class InventoryRow(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None
    printing: str | None
    ratio: str | None
    variant_type: str | None
    cover_artist: str | None
    retailer: str
    order_date: date
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    gain_loss: Decimal | None
    grade_status: str
    hold_status: str
    star_rating: int | None
    condition_notes: str | None


class InventoryListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[InventoryRow]


class InventorySummaryResponse(BaseModel):
    total_copies: int
    total_cost_basis: Decimal
    total_current_fmv: Decimal
    total_unrealized_gain_loss: Decimal
    raw_count: int
    graded_count: int
    hold_count: int
    sell_count: int


class InventoryDetailResponse(BaseModel):
    inventory_copy_id: int
    copy_number: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None
    printing: str | None
    ratio: str | None
    variant_type: str | None
    cover_artist: str | None
    retailer: str
    order_date: date
    source_type: str | None
    acquisition_cost: Decimal
    current_fmv: Decimal | None
    gain_loss: Decimal | None
    grade_status: str
    hold_status: str
    star_rating: int | None
    condition_notes: str | None
    order_id: int
    order_item_id: int
    variant_id: int
    created_at: datetime


class InventoryFmvSnapshotResponse(BaseModel):
    id: int
    previous_fmv: Decimal | None
    new_fmv: Decimal
    changed_at: datetime
    source: str


class PortfolioPerformanceItem(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None
    current_fmv: Decimal | None
    gain_loss: Decimal | None


class PortfolioPerformanceResponse(BaseModel):
    total_cost_basis: Decimal
    total_current_fmv: Decimal
    total_unrealized_gain_loss: Decimal
    top_gainers: list[PortfolioPerformanceItem]
    top_losers: list[PortfolioPerformanceItem]
    highest_value_books: list[PortfolioPerformanceItem]


class InventoryUpdate(BaseModel):
    current_fmv: Decimal | None = Field(default=None, ge=0)
    hold_status: Literal["hold", "sell", "sold"] | None = None
    star_rating: int | None = Field(default=None, ge=1, le=5)
    grade_status: Literal["raw", "submitted", "graded"] | None = None
    condition_notes: str | None = Field(default=None, max_length=2000)


class BulkInventoryUpdateRequest(BaseModel):
    inventory_copy_ids: list[int] = Field(min_length=1)
    updates: InventoryUpdate


class BulkInventoryUpdateResponse(BaseModel):
    updated_count: int
