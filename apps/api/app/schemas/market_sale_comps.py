from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_sale_comp_eligibility import (
    MarketCompCanonicalMatchState,
    MarketCompEligibilityClassification,
    MarketCompEligibilityStatus,
    MarketSaleCompEligibilityRead,
)
from app.schemas.market_fmv import MarketFmvSnapshotSummaryRead
from app.schemas.market_sale_match_suggestions import MarketSaleMatchSuggestionRead
from app.schemas.market_sales import MarketSaleNormalizationIssueRead, MarketSaleRead, MarketSaleSummaryRead

MarketComparableScope = Literal["raw", "graded", "graded_by_company", "graded_by_grade"]
MarketComparableClassification = Literal[
    "included_comp",
    "excluded_duplicate",
    "excluded_stale",
    "excluded_wrong_grade",
    "excluded_wrong_scope",
    "excluded_unresolved_identity",
    "excluded_unsupported_currency",
    "excluded_missing_price",
    "excluded_review_required",
]

MarketComparableRecencyBucket = Literal["fresh", "recent", "aged", "stale"]
MarketComparablePriceSpreadBucket = Literal["tight", "moderate", "wide", "volatile"]
MarketComparableSourceDiversityBucket = Literal["single_source", "low", "medium", "high"]
MarketComparableGradeConsistencyBucket = Literal["consistent", "mixed", "mismatched"]
MarketComparableDuplicateRiskBucket = Literal["low", "medium", "high"]


class MarketComparableQualitySignalsRead(BaseModel):
    comp_count: int = 0
    included_count: int = 0
    excluded_count: int = 0
    source_diversity_count: int = 0
    source_diversity_bucket: MarketComparableSourceDiversityBucket = "single_source"
    sale_recency_days: int | None = None
    sale_recency_bucket: MarketComparableRecencyBucket = "stale"
    price_spread: Decimal = Decimal("0")
    price_spread_ratio: float = 0.0
    price_spread_bucket: MarketComparablePriceSpreadBucket = "tight"
    grade_consistency_bucket: MarketComparableGradeConsistencyBucket = "consistent"
    duplicate_risk_bucket: MarketComparableDuplicateRiskBucket = "low"
    volatility_signal: str = "stable"
    stale_data_warning: bool = False


class MarketComparableSaleRead(MarketSaleCompEligibilityRead):
    market_sale_record_id: int | None = None
    comp_classification: MarketComparableClassification
    comp_reason: str
    comp_scope: MarketComparableScope
    comp_group_key: str
    comp_group_label: str
    comp_window_start: date | None = None
    comp_window_end: date | None = None
    comp_included: bool
    comp_group_order: int = 0
    comp_evidence_json: dict[str, Any] = Field(default_factory=dict)


class MarketComparableGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_key: str
    group_label: str
    metadata_identity_key: str | None = None
    canonical_issue_id: int | None = None
    comp_scope: MarketComparableScope
    grading_company: str | None = None
    normalized_grade: str | None = None
    currency_code: str
    sale_window_start: date | None = None
    sale_window_end: date | None = None
    included_count: int = 0
    excluded_count: int = 0
    comp_count: int = 0
    source_names: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    quality_signals: MarketComparableQualitySignalsRead = Field(default_factory=MarketComparableQualitySignalsRead)
    included_comps: list[MarketComparableSaleRead] = Field(default_factory=list)
    excluded_comps: list[MarketComparableSaleRead] = Field(default_factory=list)


class MarketComparableListResponse(BaseModel):
    items: list[MarketComparableGroupRead] = Field(default_factory=list)
    total_groups: int = 0
    total_comps: int = 0
    by_classification: dict[MarketComparableClassification, int] = Field(default_factory=dict)
    by_scope: dict[MarketComparableScope, int] = Field(default_factory=dict)


class MarketComparableSnapshotCompsResponse(BaseModel):
    snapshot: MarketFmvSnapshotSummaryRead
    items: list[MarketComparableGroupRead] = Field(default_factory=list)
    total_groups: int = 0
    total_comps: int = 0
    by_classification: dict[MarketComparableClassification, int] = Field(default_factory=dict)
    by_scope: dict[MarketComparableScope, int] = Field(default_factory=dict)


class MarketComparableSummaryRead(MarketSaleSummaryRead):
    comp_classification: MarketComparableClassification
    comp_scope: MarketComparableScope
    comp_included: bool
    comp_reason: str


class MarketComparableSaleEvidenceRead(BaseModel):
    review_status: str
    eligibility_status: MarketCompEligibilityStatus
    eligibility_classification: MarketCompEligibilityClassification
    canonical_match_state: MarketCompCanonicalMatchState
    eligibility_reasons: list[str] = Field(default_factory=list)
    normalization_issues: list[MarketSaleNormalizationIssueRead] = Field(default_factory=list)
    match_suggestions: list[MarketSaleMatchSuggestionRead] = Field(default_factory=list)

