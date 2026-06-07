"""P88 marketplace foundation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MarketplaceSourceType = Literal["MANUAL_IMPORT", "API", "SEARCH", "FUTURE_SCAN"]
MarketplaceSourceStatus = Literal["ACTIVE", "STALE", "INVALID", "REMOVED"]


class BuyOpportunityImportUrlPayload(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    notes: str = Field(default="", max_length=512)
    opportunity_id: int | None = None


class MarketplaceOpportunitySourceRead(BaseModel):
    id: int
    owner_user_id: int
    opportunity_id: int | None
    marketplace: str
    marketplace_display_name: str
    source_type: MarketplaceSourceType
    source_url: str
    external_listing_id: str
    source_status: MarketplaceSourceStatus
    notes: str
    created_at: datetime
    updated_at: datetime


class MarketplaceImportUrlResponse(BaseModel):
    message: str
    source: MarketplaceOpportunitySourceRead


class MarketplaceOpportunitySourceListResponse(BaseModel):
    items: list[MarketplaceOpportunitySourceRead]
    total_items: int
    limit: int = 50
    offset: int = 0


class EbayIntegrationStatusRead(BaseModel):
    status: Literal["Configured", "Not Configured"]
    environment: str
    client_id_present: bool
    client_secret_present: bool
    detail: str


class MarketplaceImportAuditRow(BaseModel):
    id: int
    imported_url: str
    marketplace: str
    marketplace_display_name: str
    user_id: int
    user_email: str
    status: str
    source_type: str
    notes: str
    created_at: datetime


class MarketplaceImportAuditListResponse(BaseModel):
    items: list[MarketplaceImportAuditRow]
    total_items: int
    limit: int = 100
    offset: int = 0
