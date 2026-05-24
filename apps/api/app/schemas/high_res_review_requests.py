"""P34-03 deterministic high-resolution scan review ledger (flatbed workflows; no OCR/match enqueue)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.cover_images import CoverImageRead


HighResReviewRequestReason = Literal[
    "low_quality_scan",
    "failed_ocr",
    "poor_match_confidence",
    "valuable_review_candidate",
    "manual_review",
    "rescan_required",
]


HighResReviewRequestStatus = Literal[
    "pending",
    "scanned",
    "linked",
    "review_complete",
    "cancelled",
]


HighResReviewRequestPriority = Literal["high", "medium", "low"]


class HighResReviewRequestCreatePayload(BaseModel):
    """Exactly one provenance path should be supplied (inventory-only is valid). Additional references are cross-checked."""

    inventory_copy_id: int | None = Field(
        default=None,
        ge=1,
        description="Direct inventory anchor.",
    )
    source_cover_image_id: int | None = Field(default=None, ge=1)
    source_scan_session_item_id: int | None = Field(default=None, ge=1)
    source_ocr_quality_analysis_id: int | None = Field(default=None, ge=1)
    source_inventory_risk_type: str | None = Field(default=None, max_length=80)
    source_action_center_category: str | None = Field(default=None, max_length=80)

    request_reason: HighResReviewRequestReason
    priority: HighResReviewRequestPriority = "medium"
    notes: str | None = Field(default=None, max_length=8000)


class HighResReviewRequestRead(BaseModel):
    """Full read model with nested cover payloads for deterministic side-by-side review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int

    inventory_copy_id: int
    source_cover_image_id: int | None = None
    source_scan_session_item_id: int | None = None
    source_ocr_quality_analysis_id: int | None = None
    source_inventory_risk_type: str | None = None
    source_action_center_category: str | None = None

    attach_scan_session_id: int | None = None
    attach_scan_session_item_id: int | None = None
    high_res_cover_image_id: int | None = None

    request_reason: HighResReviewRequestReason
    status: HighResReviewRequestStatus
    priority: HighResReviewRequestPriority

    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    source_cover_scan: CoverImageRead | None = Field(
        default=None,
        description="Original / bulk-linked cover retained for baseline comparison.",
    )
    review_high_res_scan: CoverImageRead | None = Field(
        default=None,
        description="Preferred review image once attached.",
    )


class HighResReviewRequestSummaryRead(BaseModel):
    """Light listing row (omit heavy nested payloads)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    inventory_copy_id: int
    source_cover_image_id: int | None = None
    high_res_cover_image_id: int | None = None

    attach_scan_session_id: int | None = None

    request_reason: HighResReviewRequestReason
    status: HighResReviewRequestStatus
    priority: HighResReviewRequestPriority
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class HighResReviewRequestListResponse(BaseModel):
    requests: list[HighResReviewRequestSummaryRead]


class HighResReviewRequestStatsRead(BaseModel):
    """Operational queue rollups keyed by deterministic status literals."""

    by_status: dict[str, int] = Field(
        ...,
        description="Counts include only rows visible to this query scope (owner vs ops).",
    )




