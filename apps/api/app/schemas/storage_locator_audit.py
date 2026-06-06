"""P79-02 locator, box contents, audit, and label schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class P79LocatorPathRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room: str | None = None
    rack: str | None = None
    shelf: str | None = None
    box: str | None = None
    section: str | None = None
    slot: int | None = None
    location_path_text: str = ""


class P79LocatorMatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    title: str
    series_name: str
    issue_number: str
    variant_label: str
    publisher: str
    assignment_status: str
    path: P79LocatorPathRead
    assigned_at: datetime | None = None
    assignment_confidence: str
    is_duplicate_assignment: bool = False
    duplicate_matches: list[int] = Field(default_factory=list)
    box_id: int | None = None


class P79InventoryLocatorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    items: list[P79LocatorMatchRead] = Field(default_factory=list)
    total_items: int
    unassigned_count: int = 0


class P79BoxContentRowRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_copy_id: int
    slot_number: int
    section: str
    series_name: str
    issue_number: str
    variant_label: str
    estimated_fmv: Decimal | None = None
    flag: str | None = None


class P79BoxSectionGroupRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str
    items: list[P79BoxContentRowRead] = Field(default_factory=list)


class P79BoxContentsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    box_id: int
    box_name: str
    capacity: int
    total_count: int
    utilization_pct: float
    total_estimated_fmv: Decimal
    sections: list[P79BoxSectionGroupRead] = Field(default_factory=list)
    flagged_rows: list[P79BoxContentRowRead] = Field(default_factory=list)


class P79StorageAuditCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_name: str = Field(min_length=1, max_length=160)
    scope_box_id: int | None = None
    scope_location_id: int | None = None


class P79StorageAuditRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    audit_name: str
    scope_kind: str
    scope_location_id: int | None
    scope_box_id: int | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    expected_count: int
    verified_count: int
    missing_count: int
    unexpected_count: int


class P79StorageAuditListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[P79StorageAuditRead] = Field(default_factory=list)
    total_items: int


class P79StorageAuditDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session: P79StorageAuditRead
    entries: list["P79StorageAuditEntryRead"] = Field(default_factory=list)
    detection_summary: dict[str, int] = Field(default_factory=dict)


class P79StorageAuditEntryRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    inventory_copy_id: int | None
    storage_box_id: int | None
    slot_number: int | None
    entry_status: str
    title_snapshot: str


class P79StorageAuditActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: int | None = None
    inventory_copy_id: int | None = None
    storage_box_id: int | None = None
    slot_number: int | None = None
    notes: str = ""
    move_to_box: bool = False


class P79StorageLabelRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: int
    label_code: str
    qr_payload: str
    printable_title: str
    storage_path: str
    capacity: int | None = None
    current_count: int | None = None


class P79StorageDetectionSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unassigned_books: int
    duplicate_assignments: int
    over_capacity_boxes: int
    misplaced_candidates: int
    items: list[dict] = Field(default_factory=list)
