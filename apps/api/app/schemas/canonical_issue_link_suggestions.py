from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CanonicalIssueSuggestionType = Literal[
    "exact_identity_key",
    "normalized_title_issue_publisher",
    "normalized_title_issue",
    "relationship_context",
    "variant_family_context",
    "duplicate_scan_context",
]

CanonicalIssueSuggestionConfidenceBucket = Literal[
    "very_high",
    "high",
    "medium",
    "low",
    "very_low",
]

CanonicalIssueSuggestionReviewState = Literal["pending", "approved", "rejected", "ignored"]


class CanonicalIssueLinkSuggestionRead(BaseModel):
    id: int
    cover_image_id: int
    inventory_copy_id: int | None
    canonical_issue_id: int | None
    canonical_series_id: int | None
    canonical_publisher_id: int | None
    suggested_metadata_identity_key: str | None
    suggestion_type: CanonicalIssueSuggestionType
    confidence_bucket: CanonicalIssueSuggestionConfidenceBucket
    deterministic_score: float
    confidence_version: str
    evidence_json: dict[str, Any]
    suppression_reason: str | None
    review_state: CanonicalIssueSuggestionReviewState
    reviewed_by_user_id: int | None
    reviewed_by_email: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CanonicalIssueSuggestionGenerateResponse(BaseModel):
    cover_image_id: int
    suggestion_count: int
    suggestions: list[CanonicalIssueLinkSuggestionRead]


class CanonicalIssueSuggestionReviewActionResponse(BaseModel):
    suggestion: CanonicalIssueLinkSuggestionRead


class CanonicalIssueSuggestionOpsListResponse(BaseModel):
    suggestions: list[CanonicalIssueLinkSuggestionRead]
    review_state: CanonicalIssueSuggestionReviewState | Literal["all"]
    confidence_bucket: CanonicalIssueSuggestionConfidenceBucket | Literal["all"]
    suggestion_type: CanonicalIssueSuggestionType | Literal["all"]


class CanonicalIssueSuggestionReviewPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=4096)
