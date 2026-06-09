from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead


PurchaseSourceType = Literal[
    "FACEBOOK",
    "WHATNOT",
    "EBAY",
    "CONVENTION",
    "YARD_SALE",
    "COLLECTION_BUY",
    "LOCAL_COMIC_SHOP",
    "OTHER",
]
LiveCaptureSource = Literal["WEBCAM", "MOBILE_CAMERA", "CONVENTION_SCAN"]
ReceivingAllocationMethod = Literal["equal", "manual", "key_weighted"]
ReceivingPurchaseMode = Literal["existing", "new"]


class ReceivingSessionCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    total_items: int
    verified_items: int
    review_items: int
    unknown_items: int
    confirmed_items: int
    skipped_items: int
    capture_source: LiveCaptureSource | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    session_notes: str | None = None
    purchase_order_id: int | None = None
    purchase_mode: ReceivingPurchaseMode | None = None
    purchase_source_type: PurchaseSourceType | None = None
    purchase_label: str | None = None
    seller_name: str | None = None
    purchase_date: date | None = None
    amount_paid: Decimal | None = None
    shipping_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    purchase_notes: str | None = None
    allocation_method: ReceivingAllocationMethod | None = None
    allocation_details_json: dict[str, Any] = Field(default_factory=dict)
    inventory_created_count: int = 0
    live_capture_stats_json: dict[str, Any] = Field(default_factory=dict)


class ReceivingSessionSummaryRead(ReceivingSessionCreateResponse):
    pass


class ReceivingSessionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receiving_session_id: int
    sequence_index: int
    source_filename: str | None = None
    mime_type: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    image_sha256: str | None = None
    capture_source: LiveCaptureSource | None = None
    frame_fingerprint: str | None = None
    frame_sequence_index: int | None = None
    stable_frame_count: int = 0
    recognition_bucket: str
    status: str
    recognition_confidence: float | None = None
    recognition_latency_ms: int | None = None
    capture_started_at: datetime | None = None
    capture_completed_at: datetime | None = None
    recognition_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    candidate_snapshot_json: list[dict[str, Any]] = Field(default_factory=list)
    selected_candidate_index: int | None = None
    selected_candidate_json: dict[str, Any] | None = None
    inventory_copy_id: int | None = None
    duplicate_of_item_id: int | None = None
    duplicate_suppressed: bool = False
    action_taken: str | None = None
    action_reason: str | None = None
    capture_metadata_json: dict[str, Any] = Field(default_factory=dict)
    uploaded_at: datetime
    recognized_at: datetime | None = None
    confirmed_at: datetime | None = None
    skipped_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReceivingSessionDetailRead(ReceivingSessionSummaryRead):
    items: list[ReceivingSessionItemRead] = Field(default_factory=list)


class ReceivingSessionCreatePayload(BaseModel):
    notes: str | None = None
    capture_source: LiveCaptureSource | None = None


class ReceivingUploadResponse(BaseModel):
    session: ReceivingSessionDetailRead
    uploaded_count: int


class ReceivingConfirmPayload(BaseModel):
    item_id: int
    decision: Literal["confirm", "wrong_match"] = "confirm"
    selected_candidate_index: int | None = None
    note: str | None = None


class ReceivingSkipPayload(BaseModel):
    item_id: int
    reason: str | None = None


class ReceivingManualAllocationItem(BaseModel):
    item_id: int
    amount: Decimal = Field(ge=0)


class ReceivingPurchaseAssignmentPayload(BaseModel):
    mode: ReceivingPurchaseMode = "new"
    existing_order_id: int | None = None
    source_type: PurchaseSourceType | None = None
    purchase_label: str | None = None
    seller_name: str | None = None
    purchase_date: date | None = None
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0)
    shipping_amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None
    allocation_method: ReceivingAllocationMethod = "equal"
    manual_allocations: list[ReceivingManualAllocationItem] = Field(default_factory=list)


class ReceivingCompletionSummaryRead(BaseModel):
    session: ReceivingSessionSummaryRead
    confirmed_inventory_count: int
    inventory_copy_ids: list[int] = Field(default_factory=list)
    top_additions: list[str] = Field(default_factory=list)
    order_id: int | None = None


class ReceivingActionResponse(BaseModel):
    session: ReceivingSessionDetailRead
    item: ReceivingSessionItemRead

