from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.inventory_intelligence import KeyedCount, OwnershipState

InventoryRiskType = Literal[
    "needs_canonical_review",
    "needs_conflict_review",
    "needs_scan",
    "needs_ocr_retry",
    "needs_cover_processing_review",
    "preorder_missing_release_date",
    "released_not_received",
    "duplicate_uncertainty",
    "run_gap_detected",
    "low_quality_scan",
    "high_confidence_match_unreviewed",
]

InventoryRiskPriority = Literal["critical", "high", "medium", "low", "info"]
InventoryRiskStatus = Literal["open"]


class InventoryRiskRead(BaseModel):
    risk_key: str
    inventory_copy_id: int
    cover_image_id: int | None = None
    risk_type: InventoryRiskType
    priority: InventoryRiskPriority
    status: InventoryRiskStatus = "open"
    ownership_state: OwnershipState
    publisher: str
    title: str
    issue_number: str
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class InventoryRiskSummaryItem(BaseModel):
    inventory_copy_id: int
    publisher: str
    title: str
    issue_number: str
    ownership_state: OwnershipState
    highest_priority: InventoryRiskPriority
    risk_count: int = Field(ge=0)
    risk_types: list[InventoryRiskType] = Field(default_factory=list)
    evidence_preview: list[str] = Field(default_factory=list)


class InventoryRiskSummary(BaseModel):
    scope_user_id: int | None
    scope: str
    generated_as_of_date: str
    total_inventory_copies: int = Field(default=0, ge=0)
    total_risk_items: int = Field(default=0, ge=0)
    copies_with_risk: int = Field(default=0, ge=0)
    critical_copies: int = Field(default=0, ge=0)
    high_copies: int = Field(default=0, ge=0)
    medium_copies: int = Field(default=0, ge=0)
    low_copies: int = Field(default=0, ge=0)
    info_copies: int = Field(default=0, ge=0)
    by_priority: list[KeyedCount] = Field(default_factory=list)
    by_risk_type: list[KeyedCount] = Field(default_factory=list)
    top_action_items: list[InventoryRiskSummaryItem] = Field(default_factory=list)


class InventoryRiskListResponse(BaseModel):
    scope_user_id: int | None
    scope: str
    generated_as_of_date: str
    total_count: int = Field(default=0, ge=0)
    priority: InventoryRiskPriority | Literal["all"]
    risk_type: InventoryRiskType | Literal["all"]
    ownership_state: OwnershipState | Literal["all"]
    publisher: str | None = None
    in_hand_only: bool = False
    open_only: bool = True
    summary: InventoryRiskSummary
    risks: list[InventoryRiskRead] = Field(default_factory=list)

