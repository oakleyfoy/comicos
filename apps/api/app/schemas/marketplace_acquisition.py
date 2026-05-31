from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MarketplaceAcquisitionSourceType = Literal[
    "EBAY",
    "WHATNOT",
    "MYCOMICSHOP",
    "COMICLINK",
    "COMICCONNECT",
    "MANUAL",
    "OTHER",
]
MarketplaceCandidateRecommendation = Literal["BUY", "WATCH", "PASS"]
MarketplaceCandidateStatus = Literal["NEW", "REVIEWED", "IGNORED", "ACQUIRED"]


class MarketplaceSourceRead(BaseModel):
    id: int
    name: str
    source_type: MarketplaceAcquisitionSourceType
    base_url: str | None
    is_active: bool


class MarketplaceAcquisitionCandidateCreate(BaseModel):
    marketplace_source_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    publisher: str | None = None
    series_name: str | None = None
    issue_number: str | None = None
    variant_description: str | None = None
    listing_url: str | None = None
    asking_price: float | None = Field(default=None, ge=0)
    shipping_price: float | None = Field(default=None, ge=0)
    total_price: float | None = Field(default=None, ge=0)
    condition_description: str | None = None
    grade_label: str | None = None
    seller_name: str | None = None


class MarketplaceAcquisitionCandidateUpdate(BaseModel):
    marketplace_source_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    publisher: str | None = None
    series_name: str | None = None
    issue_number: str | None = None
    variant_description: str | None = None
    listing_url: str | None = None
    asking_price: float | None = Field(default=None, ge=0)
    shipping_price: float | None = Field(default=None, ge=0)
    total_price: float | None = Field(default=None, ge=0)
    condition_description: str | None = None
    grade_label: str | None = None
    seller_name: str | None = None
    status: MarketplaceCandidateStatus | None = None


class MarketplaceAcquisitionCandidateRead(BaseModel):
    id: int
    owner_id: int
    marketplace_source_id: int | None
    source_name: str | None
    source_type: MarketplaceAcquisitionSourceType | None
    acquisition_opportunity_id: int | None
    title: str
    publisher: str | None
    series_name: str | None
    issue_number: str | None
    variant_description: str | None
    listing_url: str | None
    asking_price: float | None
    shipping_price: float | None
    total_price: float | None
    condition_description: str | None
    grade_label: str | None
    seller_name: str | None
    match_confidence: float
    value_score: float
    recommendation: MarketplaceCandidateRecommendation
    rationale: str
    status: MarketplaceCandidateStatus
    created_at: str
    updated_at: str


class MarketplaceAcquisitionSummaryRead(BaseModel):
    total_candidates: int
    by_recommendation: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    average_match_confidence: float = 0.0
    average_value_score: float = 0.0
    sources: list[MarketplaceSourceRead] = Field(default_factory=list)


class MarketplaceAcquisitionListRead(BaseModel):
    items: list[MarketplaceAcquisitionCandidateRead]
    total_items: int
    limit: int
    offset: int
