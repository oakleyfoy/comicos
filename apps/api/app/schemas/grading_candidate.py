"""P37-01 schemas for operational grading candidate registry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

GradingCandidateStatus = Literal[
    "CANDIDATE",
    "REVIEWING",
    "READY_FOR_SUBMISSION",
    "SUBMITTED",
    "GRADED",
    "REJECTED",
    "ARCHIVED",
]
GradingTargetGrader = Literal["PSA", "CGC", "CBCS", "RAW_ONLY"]
GradingCandidatePriority = Literal["LOW", "MEDIUM", "HIGH", "ELITE"]

GradingEvidenceType = Literal[
    "FMV",
    "SALE",
    "LIQUIDITY",
    "LISTING_INTELLIGENCE",
    "SCAN_REFERENCE",
    "MANUAL_REVIEW",
    "CONVENTION_ACTIVITY",
]

GradingLifecycleEventType = Literal[
    "CREATED",
    "REVIEW_STARTED",
    "READY_FOR_SUBMISSION",
    "SUBMITTED",
    "GRADED",
    "REJECTED",
    "ARCHIVED",
    "UPDATED",
]


P72GradingRecommendation = Literal["GRADE", "PRESS_AND_GRADE", "WATCH", "DO_NOT_GRADE"]
P72PressingRecommendation = Literal["PRESS", "DO_NOT_PRESS"]


class P72GradingCandidateSummary(BaseModel):
    """P72-01 discovery summary (advisory; no workflow mutation)."""

    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    recommendation: P72GradingRecommendation | str
    pressing_recommendation: P72PressingRecommendation | str
    grading_score: float
    expected_roi_pct: float


class GradingCandidateDashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_candidates: int
    pipeline_active_count: int
    ready_for_submission_count: int
    submitted_count: int
    graded_count: int
    elite_priority_count: int


class InventoryGradingCandidateBadge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grading_candidate_id: int
    status: str
    target_grader: str
    candidate_priority: str
    is_pipeline_active: bool


class GradingCandidateEvidenceCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_type: GradingEvidenceType | str = Field(..., min_length=2, max_length=32)
    lineage_domain: str = Field(..., min_length=1, max_length=96)
    lineage_key: str = Field(..., min_length=1, max_length=256)
    reference_json: dict[str, object] = Field(default_factory=dict)


class GradingCandidateEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_candidate_id: int
    evidence_type: str
    lineage_domain: str
    lineage_key: str
    reference_json: dict[str, object]
    created_at: datetime


class GradingCandidateEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingCandidateEvidenceRead]
    total_items: int
    limit: int
    offset: int


class GradingCandidateLifecycleEventRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_candidate_id: int
    event_type: str
    from_status: str | None
    to_status: str | None
    payload_json: dict[str, object]
    created_at: datetime


class GradingCandidateLifecycleEventListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingCandidateLifecycleEventRead]
    total_items: int
    limit: int
    offset: int


class GradingCandidateSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    grading_candidate_id: int
    assumptions_json: dict[str, object]
    evidence_count: int
    checksum: str
    created_at: datetime


class GradingCandidateCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: int = Field(..., ge=1)
    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    target_grader: GradingTargetGrader | str = Field(..., min_length=2, max_length=16)
    target_grade: str | None = Field(default=None, max_length=32)
    estimated_raw_value: Decimal | None = Field(default=None, ge=Decimal("0"))
    estimated_graded_value: Decimal | None = Field(default=None, ge=Decimal("0"))
    estimated_spread: Decimal | None = None
    estimated_grading_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    estimated_roi: Decimal | None = None
    candidate_priority: GradingCandidatePriority | str = Field(..., min_length=2, max_length=16)
    rationale: str | None = Field(default=None, max_length=8000)
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class GradingCandidatePatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_comic_issue_id: int | None = Field(default=None, ge=1)
    target_grader: GradingTargetGrader | str | None = Field(
        default=None, min_length=2, max_length=16
    )
    target_grade: str | None = Field(default=None, max_length=32)
    estimated_raw_value: Decimal | None = Field(default=None, ge=Decimal("0"))
    estimated_graded_value: Decimal | None = Field(default=None, ge=Decimal("0"))
    estimated_spread: Decimal | None = None
    estimated_grading_cost: Decimal | None = Field(default=None, ge=Decimal("0"))
    estimated_roi: Decimal | None = None
    candidate_priority: GradingCandidatePriority | str | None = Field(
        default=None, min_length=2, max_length=16
    )
    rationale: str | None = Field(default=None, max_length=8000)


class GradingCandidateRejectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=8000)


class GradingCandidateGradePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(default=None, max_length=8000)


class GradingCandidateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    owner_user_id: int
    inventory_item_id: int
    canonical_comic_issue_id: int | None
    status: str
    target_grader: str
    target_grade: str | None
    estimated_raw_value: Decimal | None
    estimated_graded_value: Decimal | None
    estimated_spread: Decimal | None
    estimated_grading_cost: Decimal | None
    estimated_roi: Decimal | None
    candidate_priority: str
    rationale: str | None
    replay_key: str | None

    evidence_count: int
    latest_snapshot_checksum: str | None

    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    graded_at: datetime | None
    archived_at: datetime | None


class GradingCandidateDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: GradingCandidateRead
    lifecycle_events: list[GradingCandidateLifecycleEventRead]
    snapshots: list[GradingCandidateSnapshotRead]
    evidence: list[GradingCandidateEvidenceRead]


class GradingCandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingCandidateRead]
    total_items: int
    limit: int
    offset: int
