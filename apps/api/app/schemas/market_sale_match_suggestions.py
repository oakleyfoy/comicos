from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.market_sales import MarketSaleNormalizationStatus, MarketSourceType

MarketSaleMatchSuggestionType = Literal[
    "exact_identity_key",
    "normalized_title_issue_publisher",
    "normalized_title_issue",
    "publisher_series_issue",
    "barcode_supported",
    "inventory_context_supported",
    "unresolved_ambiguous",
]

MarketSaleMatchSuggestionConfidenceBucket = Literal["very_high", "high", "medium", "low", "very_low"]
MarketSaleMatchSuggestionReviewState = Literal["pending", "approved", "rejected", "ignored"]


class MarketSaleMatchSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_sale_record_id: int
    market_source_id: int
    source_name: str
    source_type: MarketSourceType
    source_listing_id: str | None = None
    listing_type: str
    raw_title: str
    normalized_title: str | None = None
    raw_issue: str
    normalized_issue: str | None = None
    raw_publisher: str | None = None
    normalized_publisher: str | None = None
    raw_variant: str | None = None
    normalized_variant: str | None = None
    raw_grade: str | None = None
    normalized_grade: str | None = None
    raw_cert_number: str | None = None
    normalized_cert_number: str | None = None
    sale_price: Decimal | None = None
    shipping_price: Decimal | None = None
    total_price: Decimal | None = None
    currency_code: str
    sale_date: date | None = None
    is_graded: bool
    grading_company: str | None = None
    is_signed: bool
    normalization_status: MarketSaleNormalizationStatus
    normalization_issue_count: int = 0
    canonical_issue_id: int | None = None
    canonical_series_id: int | None = None
    canonical_publisher_id: int | None = None
    suggested_identity_key: str | None = None
    suggestion_type: MarketSaleMatchSuggestionType
    confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket
    deterministic_score: float
    confidence_version: str
    evidence_json: dict[str, Any]
    review_state: MarketSaleMatchSuggestionReviewState
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MarketSaleMatchSuggestionGenerateResponse(BaseModel):
    sale_id: int
    suggestion_count: int
    suggestions: list[MarketSaleMatchSuggestionRead]


class MarketSaleMatchSuggestionReviewActionResponse(BaseModel):
    suggestion: MarketSaleMatchSuggestionRead


class MarketSaleMatchSuggestionOpsListResponse(BaseModel):
    suggestions: list[MarketSaleMatchSuggestionRead]
    review_state: MarketSaleMatchSuggestionReviewState | Literal["all"]
    confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | Literal["all"]
    suggestion_type: MarketSaleMatchSuggestionType | Literal["all"]
    total_count: int
