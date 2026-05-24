from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

OwnershipState = Literal[
    "in_hand",
    "preorder",
    "ordered_not_received",
    "cancelled",
    "unknown_state",
]
InventoryHealthCategory = Literal["healthy", "needs_review", "incomplete", "blocked"]


class KeyedCount(BaseModel):
    """Single bucket inside a deterministic breakdown dimension."""

    key: str | None = None
    count: int = Field(ge=0)


class InventoryIntelligenceSummary(BaseModel):
    total_inventory_copies: int = Field(default=0, ge=0)
    ownership_in_hand: int = Field(default=0, ge=0)
    ownership_preorder: int = Field(default=0, ge=0)
    ownership_ordered_not_received: int = Field(default=0, ge=0)
    ownership_cancelled: int = Field(default=0, ge=0)
    ownership_unknown_state: int = Field(default=0, ge=0)
    graded_copies: int = Field(default=0, ge=0)
    raw_copies: int = Field(default=0, ge=0)
    scanned_copies: int = Field(default=0, ge=0)
    unscanned_copies: int = Field(default=0, ge=0)
    ocr_complete_copies: int = Field(default=0, ge=0)
    ocr_pending_copies: int = Field(default=0, ge=0)
    cover_processing_failed_copies: int = Field(
        default=0,
        ge=0,
        description=(
            "Primary cover image processing ended in deterministic failed status "
            "(possible corrupt/unreadable asset)."
        ),
    )
    ocr_failed_copies: int = Field(
        default=0,
        ge=0,
        description="Latest OCR result for primary cover marked failed.",
    )
    unresolved_relationship_conflicts: int = Field(default=0, ge=0)
    unresolved_canonical_suggestions: int = Field(default=0, ge=0)
    unresolved_duplicate_inventory_groups: int = Field(default=0, ge=0)
    unresolved_duplicate_scan_clusters: int = Field(default=0, ge=0)
    unresolved_variant_family_clusters: int = Field(default=0, ge=0)


class InventoryIntelligenceHealthSummary(BaseModel):
    healthy: int = Field(default=0, ge=0)
    needs_review: int = Field(default=0, ge=0)
    incomplete: int = Field(default=0, ge=0)
    blocked: int = Field(default=0, ge=0)


class InventoryIntelligenceBreakdown(BaseModel):
    by_publisher: list[KeyedCount] = Field(default_factory=list)
    by_year: list[KeyedCount] = Field(default_factory=list)
    by_release_status: list[KeyedCount] = Field(default_factory=list)
    by_order_status: list[KeyedCount] = Field(default_factory=list)
    by_grade_status: list[KeyedCount] = Field(default_factory=list)
    by_ownership_state: list[KeyedCount] = Field(default_factory=list)
    unhealthy_sample_inventory_copy_ids: list[int] = Field(default_factory=list)


class InventoryCopyIntelligenceSignals(BaseModel):
    """Per-copy read-only operational signals (computed, never persisted)."""

    ownership_state: OwnershipState
    inventory_health: InventoryHealthCategory
    has_cover_scan: bool
    preorder_missing_release_calendar: bool
    has_open_relationship_conflict: bool
    has_pending_canonical_suggestion: bool
    in_pending_duplicate_inventory_group: bool
    touches_probable_duplicate_scan_cluster: bool
    touches_probable_variant_family_cluster: bool

