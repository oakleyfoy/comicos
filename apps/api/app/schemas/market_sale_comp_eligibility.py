from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.market_sale_match_suggestions import (
    MarketSaleMatchSuggestionConfidenceBucket,
    MarketSaleMatchSuggestionRead,
    MarketSaleMatchSuggestionReviewState,
)
from app.schemas.market_sales import (
    MarketSaleRead,
    MarketSaleReviewStatus,
    MarketSaleSummaryRead,
)

MarketCompEligibilityStatus = Literal["eligible", "ineligible", "needs_review"]
MarketCompEligibilityClassification = Literal[
    "eligible_raw_comp",
    "eligible_graded_comp",
    "ineligible_missing_price",
    "ineligible_unsupported_currency",
    "ineligible_unresolved_identity",
    "ineligible_duplicate_listing",
    "ineligible_ignored_record",
    "ineligible_invalid_grade",
    "needs_review_before_comp",
]
MarketCompCanonicalMatchState = Literal["approved", "high_confidence", "needs_review", "missing"]

_ELIGIBILITY_STATUS_ORDER: tuple[MarketCompEligibilityStatus, ...] = ("eligible", "needs_review", "ineligible")
_ELIGIBILITY_CLASSIFICATION_ORDER: tuple[MarketCompEligibilityClassification, ...] = (
    "eligible_graded_comp",
    "eligible_raw_comp",
    "needs_review_before_comp",
    "ineligible_missing_price",
    "ineligible_unsupported_currency",
    "ineligible_unresolved_identity",
    "ineligible_duplicate_listing",
    "ineligible_ignored_record",
    "ineligible_invalid_grade",
)


class MarketSaleCompEligibilitySummaryRead(MarketSaleSummaryRead):
    review_status: MarketSaleReviewStatus
    eligibility_status: MarketCompEligibilityStatus
    eligibility_classification: MarketCompEligibilityClassification
    eligibility_reasons: list[str] = Field(default_factory=list)
    canonical_match_state: MarketCompCanonicalMatchState
    canonical_match_suggestion_id: int | None = None
    canonical_match_confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | None = None
    canonical_match_review_state: MarketSaleMatchSuggestionReviewState | None = None
    canonical_match_deterministic_score: float | None = None
    match_suggestion_count: int = 0


class MarketSaleCompEligibilityRead(MarketSaleRead):
    review_status: MarketSaleReviewStatus
    eligibility_status: MarketCompEligibilityStatus
    eligibility_classification: MarketCompEligibilityClassification
    eligibility_reasons: list[str] = Field(default_factory=list)
    canonical_match_state: MarketCompCanonicalMatchState
    canonical_match_suggestion_id: int | None = None
    canonical_match_confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | None = None
    canonical_match_review_state: MarketSaleMatchSuggestionReviewState | None = None
    canonical_match_deterministic_score: float | None = None
    match_suggestion_count: int = 0
    eligibility_evidence_json: dict[str, Any] = Field(default_factory=dict)
    match_suggestions: list[MarketSaleMatchSuggestionRead] = Field(default_factory=list)


class MarketSaleCompEligibilityListResponse(BaseModel):
    items: list[MarketSaleCompEligibilitySummaryRead] = Field(default_factory=list)
    total: int = 0
    by_eligibility_status: dict[MarketCompEligibilityStatus, int] = Field(default_factory=dict)
    by_eligibility_classification: dict[MarketCompEligibilityClassification, int] = Field(default_factory=dict)


def comp_eligibility_status_order() -> tuple[MarketCompEligibilityStatus, ...]:
    return _ELIGIBILITY_STATUS_ORDER


def comp_eligibility_classification_order() -> tuple[MarketCompEligibilityClassification, ...]:
    return _ELIGIBILITY_CLASSIFICATION_ORDER
