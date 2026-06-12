from __future__ import annotations

from pydantic import BaseModel, Field


class CollectionResetTableCount(BaseModel):
    label: str
    row_count: int = Field(ge=0)


class CollectionResetSummary(BaseModel):
    inventory_copies: int = 0
    orders: int = 0
    order_items: int = 0
    draft_imports: int = 0
    retailer_order_snapshots: int = 0
    retailer_order_item_snapshots: int = 0
    gmail_import_records: int = 0
    portfolio_items: int = 0
    portfolios: int = 0
    cover_images: int = 0
    receiving_sessions: int = 0
    collection_valuation_snapshots: int = 0
    inventory_fmv_snapshots: int = 0
    total_rows: int = 0


class CollectionResetRemaining(BaseModel):
    inventory_copies: int = 0
    orders: int = 0
    draft_imports: int = 0
    retailer_order_snapshots: int = 0
    gmail_import_records: int = 0
    portfolio_items: int = 0
    portfolios: int = 0


class CollectionResetPreviewResponse(BaseModel):
    status: str = "preview"
    dry_run: bool = True
    summary: CollectionResetSummary
    table_counts: list[CollectionResetTableCount] = Field(default_factory=list)
    remaining: CollectionResetRemaining


class CollectionResetExecuteRequest(BaseModel):
    confirmation_phrase: str
    acknowledge_permanent_delete: bool = False


class CollectionResetExecuteResponse(BaseModel):
    status: str
    dry_run: bool = False
    deleted: CollectionResetSummary
    deleted_by_table: list[CollectionResetTableCount] = Field(default_factory=list)
    remaining: CollectionResetRemaining
