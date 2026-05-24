"""P34-04 deterministic scan QA routing payloads (signals only — no OCR auto-enqueue)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScanQaClassification = Literal[
    "ready_for_ocr",
    "needs_high_res_review",
    "needs_rescan",
    "corrupt_or_unreadable",
    "duplicate_scan",
    "low_resolution",
    "low_contrast",
    "blurry",
    "already_processed",
    "review_required",
]

ScanQaRoutingRecommendation = Literal[
    "queue_for_ocr",
    "send_to_high_res_review",
    "request_rescan",
    "hold_for_manual_review",
    "no_action_needed",
]

ScanQaSeverity = Literal["info", "warning", "critical"]


class ScanQaItemRead(BaseModel):
    scan_session_item_id: int
    cover_image_id: int | None = None
    qa_classification: ScanQaClassification
    routing_recommendation: ScanQaRoutingRecommendation
    severity: ScanQaSeverity
    evidence_json: dict = Field(default_factory=dict)


class ScanSessionQaSummaryRead(BaseModel):
    scan_session_id: int
    owner_user_id: int
    scanner_profile: str | None = None
    persisted_run: bool = False
    items: list[ScanQaItemRead]
    totals_by_classification: dict[str, int] = Field(default_factory=dict)
    totals_by_routing: dict[str, int] = Field(default_factory=dict)


class OpsScanQaFleetSummaryRead(BaseModel):
    totals_by_classification: dict[str, int] = Field(default_factory=dict)
    totals_by_routing: dict[str, int] = Field(default_factory=dict)
    failure_and_rescan: dict[str, int] = Field(
        default_factory=dict,
        description="Derived counters for ops visibility such as corrupt, rescan-needed, duplicates.",
    )


class InventoryCoverScanQaRow(BaseModel):
    cover_image_id: int
    qa_classification: ScanQaClassification
    routing_recommendation: ScanQaRoutingRecommendation
    severity: ScanQaSeverity
    evidence_json: dict = Field(default_factory=dict)


class InventoryScanQaPanelRead(BaseModel):
    inventory_copy_id: int
    covers: list[InventoryCoverScanQaRow]
