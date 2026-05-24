from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cover_images import (
    CoverImageBarcodeCandidateRead,
    CoverImageMatchCandidateRead,
    CoverImageOcrCandidateRead,
    CoverImageOcrQualityAnalysisRead,
    CoverImageOcrReconciliationWarningRead,
)

OcrReviewItemKindLiteral = Literal[
    "ocr_candidate",
    "reconciliation_warning",
    "barcode_candidate",
    "match_candidate",
    "ocr_quality_analysis",
]


class OcrReviewQueueItem(BaseModel):
    """Single queue row with hydrated entity snapshots (exactly one entity field is populated)."""

    item_kind: OcrReviewItemKindLiteral
    entity_id: int
    cover_image_id: int
    created_at: datetime
    sort_tier: int = Field(ge=0, le=15, description="Internal ordering tier (critical/high first)")
    norm_score: float | None = Field(
        None,
        description="Descending sort helper; missing confidence modeled as negative sentinel",
    )

    extraction_version: str | None = None
    severity: str | None = None
    warning_type: str | None = None
    quality_type: str | None = None
    candidate_type: str | None = None
    confidence_bucket: str | None = None

    reconciliation_status: str | None = None
    barcode_review_state: str | None = None
    ocr_candidate_review_status: str | None = None
    acknowledged_at: datetime | None = None
    dismissed_at: datetime | None = None

    ocr_candidate: CoverImageOcrCandidateRead | None = None
    reconciliation_warning: CoverImageOcrReconciliationWarningRead | None = None
    barcode_candidate: CoverImageBarcodeCandidateRead | None = None
    match_candidate: CoverImageMatchCandidateRead | None = None
    ocr_quality_analysis: CoverImageOcrQualityAnalysisRead | None = None


class OcrReviewQueueResponse(BaseModel):
    items: list[OcrReviewQueueItem]
    total: int
    page: int
    page_size: int


class OcrReviewSummaryResponse(BaseModel):
    pending_ocr_candidates: int = Field(ge=0)
    open_reconciliation_warnings: int = Field(ge=0)
    critical_ocr_quality_analyses: int = Field(ge=0)
    pending_high_bucket_match_candidates: int = Field(ge=0)

    batches_with_failed_items: int = Field(
        ge=0,
        description="OcrBatch rows counted when failed_count>0.",
    )

    replay_changed_items_completed_runs_total: int = Field(
        ge=0,
        description="SUM(OcrReplayRun.changed_items) for completed runs scoped to viewer.",
    )


class BulkIdsPayload(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class BulkMutationResult(BaseModel):
    succeeded: list[int] = Field(default_factory=list)
    skipped: dict[str, str] = Field(
        default_factory=dict,
        description="Keyed by string entity id → skip reason.",
    )

