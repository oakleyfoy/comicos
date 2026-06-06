"""P80-02 mobile inventory operations API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class P80IntakeStartRequest(BaseModel):
    intake_mode: str = Field(description="ORDER, PURCHASE, or MANUAL")
    order_id: int | None = None


class P80IntakeScanRequest(BaseModel):
    session_id: int
    barcode: str


class P80IntakeCompleteRequest(BaseModel):
    session_id: int


class P80IntakeScanResultRead(BaseModel):
    session_id: int
    session: P80IntakeSessionRead | None = None
    scan_status: str
    title: str | None = None
    inventory_copy_id: int | None = None
    order_item_matched: bool = False
    created_inventory: bool = False
    duplicate_scan: bool = False
    message: str = ""


class P80IntakeSessionRead(BaseModel):
    session_id: int
    intake_mode: str
    order_id: int | None = None
    status: str
    expected_count: int
    scanned_count: int
    received_count: int
    missing_count: int
    duplicate_scan_count: int
    unknown_scan_count: int
    scans: list[dict] = Field(default_factory=list)


class P80IntakeCompleteRead(BaseModel):
    session: P80IntakeSessionRead
    status_label: str


class P80StorageSuggestRequest(BaseModel):
    inventory_copy_id: int
    box_id: int | None = None


class P80StorageSuggestionRead(BaseModel):
    inventory_copy_id: int
    recommended_box_id: int | None = None
    recommended_box_name: str | None = None
    suggested_slot_number: int | None = None
    section_label: str | None = None
    location_path_text: str | None = None
    series_grouping_score: float = 0.0
    capacity_available: bool = True
    reasons: list[str] = Field(default_factory=list)


class P80StorageAssignRequest(BaseModel):
    inventory_copy_id: int = 0
    box_id: int
    slot_number: int | None = None
    use_suggested_slot: bool = True
    barcode: str | None = None


class P80AuditStartRequest(BaseModel):
    audit_name: str
    scope_box_id: int | None = None
    scope_location_id: int | None = None


class P80AuditStartRead(BaseModel):
    audit_id: int
    audit_name: str
    expected_count: int
    scope_box_id: int | None = None
    scope_location_id: int | None = None


class P80AuditScanRequest(BaseModel):
    audit_id: int
    barcode: str


class P80AuditCompleteRequest(BaseModel):
    audit_id: int


class P80AuditScanRead(BaseModel):
    audit_id: int
    outcome: str
    inventory_copy_id: int | None = None
    entry_id: int | None = None
    title: str | None = None
    verified_count: int = 0
    unexpected_count: int = 0
    message: str = ""


class P80AuditCompleteRead(BaseModel):
    audit_id: int
    status: str
    verified_count: int
    missing_count: int
    unexpected_count: int
    duplicate_assignments: int
    audit_accuracy_pct: float


class P80MobileAuditDetailRead(BaseModel):
    session: dict
    entries: list[dict]
    detection_summary: dict
    audit_accuracy_pct: float


class P80OperationsDashboardRead(BaseModel):
    intake_received_today: int
    intake_received_this_week: int
    intake_pending_receipts: int
    storage_assigned_today: int
    storage_unassigned_inventory: int
    audit_open_sessions: int
    audit_recent_completed: int
    audit_average_accuracy_pct: float
    generated_at: datetime
