from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RelationshipConflictType = Literal[
    "duplicate_scan_vs_variant_family",
    "same_cover_vs_variant_family",
    "same_issue_vs_unrelated",
    "approved_link_vs_rejected_link",
    "canonical_suggestion_mismatch",
    "duplicate_scan_different_canonical_issue",
    "variant_family_same_fingerprint",
    "relationship_cycle_warning",
    "stale_confidence_after_decision",
    "preorder_not_in_hand_reconciliation_warning",
]

RelationshipConflictSeverity = Literal["info", "warning", "critical"]
RelationshipConflictStatus = Literal["open", "acknowledged", "dismissed", "resolved"]


class CoverRelationshipConflictRead(BaseModel):
    id: int
    conflict_type: RelationshipConflictType
    severity: RelationshipConflictSeverity
    source_cover_image_id: int | None
    related_cover_image_id: int | None
    link_decision_id: int | None
    match_candidate_id: int | None
    canonical_issue_suggestion_id: int | None
    conflict_key: str
    status: RelationshipConflictStatus
    evidence_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None
    dismissed_at: datetime | None
    resolved_at: datetime | None


class CoverRelationshipConflictListResponse(BaseModel):
    conflicts: list[CoverRelationshipConflictRead]
    severity: RelationshipConflictSeverity | Literal["all"]
    status: RelationshipConflictStatus | Literal["all"]
    conflict_type: RelationshipConflictType | Literal["all"]
    total_count: int
    open_count: int
    acknowledged_count: int
    dismissed_count: int
    resolved_count: int


class CoverRelationshipConflictDetectResponse(BaseModel):
    detected_count: int
    open_count: int
    acknowledged_count: int
    dismissed_count: int
    resolved_count: int
    conflicts: list[CoverRelationshipConflictRead]


class CoverRelationshipConflictActionResponse(BaseModel):
    conflict: CoverRelationshipConflictRead


class CoverRelationshipConflictStatusPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=4096)
