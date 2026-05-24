from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.inventory_intelligence import KeyedCount, OwnershipState

InventoryActionCenterCategory = Literal[
    "review_relationship_conflict",
    "review_canonical_suggestion",
    "review_duplicate_ownership",
    "review_duplicate_scan",
    "review_variant_family",
    "retry_ocr",
    "review_cover_processing",
    "scan_missing_cover",
    "update_preorder_metadata",
    "review_run_gap",
    "review_high_confidence_match",
]

InventoryActionLanePriority = Literal["critical", "high", "medium", "low", "info"]
InventoryReleaseStatusFilter = Literal["released", "not_released_yet", "unknown"]


class InventoryActionCenterGrouping(BaseModel):
    """Stable grouped action keys per dimension."""

    action_keys_by_inventory_copy_id: dict[int, list[str]] = Field(default_factory=dict)
    action_keys_by_cover_image_id: dict[int, list[str]] = Field(default_factory=dict)
    action_keys_by_series_key: dict[str, list[str]] = Field(default_factory=dict)
    action_keys_by_publisher: dict[str, list[str]] = Field(default_factory=dict)
    action_keys_by_ownership_state: dict[str, list[str]] = Field(default_factory=dict)
    action_keys_by_preorder_release_state: dict[str, list[str]] = Field(default_factory=dict)


class InventoryActionCenterItem(BaseModel):
    """Single deterministic workflow-visible action."""

    action_key: str = Field(description="Globally stable key for grouping and pagination.")
    action_category: InventoryActionCenterCategory
    priority: InventoryActionLanePriority
    inventory_copy_id: int
    cover_image_id: int | None = None
    publisher: str
    title: str
    issue_number: str
    ownership_state: OwnershipState
    release_status: InventoryReleaseStatusFilter
    preorder_release_state_label: str = Field(
        description="publisher-invariant deterministic bucket for preorder/release rollup.",
    )
    evidence_summary_lines: list[str] = Field(
        default_factory=list,
        description="Short deterministic excerpts derived from evidence_json.",
    )
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    source: Literal["inventory_risk", "intelligence_duplicate_scan", "intelligence_variant_family", "order_arrival"]


class InventoryActionCenterTopInventoryItem(BaseModel):
    inventory_copy_id: int
    publisher: str
    title: str
    issue_number: str
    highest_lane_priority: InventoryActionLanePriority
    ownership_state: OwnershipState
    action_count: int = Field(ge=0)
    action_categories: list[InventoryActionCenterCategory] = Field(default_factory=list)


class InventoryActionCenterSummary(BaseModel):
    scope_user_id: int | None
    scope: str
    generated_as_of_date: str
    total_inventory_copies: int = Field(default=0, ge=0)
    total_actions: int = Field(default=0, ge=0)
    copies_with_actions: int = Field(default=0, ge=0)
    critical_actions: int = Field(default=0, ge=0)
    high_actions: int = Field(default=0, ge=0)
    medium_actions: int = Field(default=0, ge=0)
    low_actions: int = Field(default=0, ge=0)
    info_actions: int = Field(default=0, ge=0)
    by_category: list[KeyedCount] = Field(default_factory=list)
    by_priority_lane: list[KeyedCount] = Field(default_factory=list)
    top_unresolved_inventory: list[InventoryActionCenterTopInventoryItem] = Field(default_factory=list)


class InventoryActionCenterListResponse(BaseModel):
    scope_user_id: int | None
    scope: str
    generated_as_of_date: str
    priority: InventoryActionLanePriority | Literal["all"] = "all"
    action_category: InventoryActionCenterCategory | Literal["all"] = "all"
    ownership_state: OwnershipState | Literal["all"] = "all"
    publisher: str | None = None
    release_status: InventoryReleaseStatusFilter | Literal["all"] = "all"
    unresolved_only: bool = True
    in_hand_only: bool = False
    inventory_copy_id_filter: int | None = Field(
        default=None,
        description="When set (detail views), aggregate is restricted to one copy.",
    )
    summary: InventoryActionCenterSummary
    grouping: InventoryActionCenterGrouping
    actions: list[InventoryActionCenterItem] = Field(default_factory=list)


class InventoryActionCenterAttachment(BaseModel):
    """Lightweight badges for inventory list/detail rows."""

    action_keys: list[str] = Field(default_factory=list)
    action_categories: list[InventoryActionCenterCategory] = Field(default_factory=list)
    highest_lane_priority: InventoryActionLanePriority | None = Field(
        default=None,
        description="Best (most severe) priority among visible actions.",
    )
    urgent_lane: bool = Field(
        default=False,
        description="True when any action lane is critical or high.",
    )
