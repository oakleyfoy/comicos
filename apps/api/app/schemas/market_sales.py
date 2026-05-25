from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MarketSaleListingType = Literal["auction", "fixed_price", "accepted_offer", "buy_it_now", "other"]
MarketSaleNormalizationStatus = Literal["raw", "partially_normalized", "normalized", "normalization_failed", "ignored"]
MarketSaleReviewStatus = Literal["pending", "reviewed", "ignored", "duplicate_flagged"]
MarketSaleGradingCompany = Literal["CGC", "CBCS", "PGX", "other"]
MarketSaleIssueType = Literal[
    "missing_issue_number",
    "ambiguous_variant",
    "invalid_grade",
    "malformed_title",
    "missing_sale_price",
    "duplicate_listing",
    "unsupported_currency",
]
MarketSaleIssueSeverity = Literal["info", "warning", "critical"]
MarketSaleReviewClassification = Literal[
    "needs_title_review",
    "needs_issue_review",
    "needs_variant_review",
    "needs_grade_review",
    "needs_price_review",
    "possible_duplicate",
    "unsupported_currency",
    "ready_for_comp_review",
    "ignored",
]
MarketSaleReviewPriority = Literal["critical", "high", "medium", "low", "info"]
MarketSaleReviewActionType = Literal["mark_reviewed", "ignore_record", "flag_duplicate", "manual_normalization_update"]
MarketSourceType = Literal["marketplace", "auction", "fixed_price", "historical_archive", "other"]
MarketSourceImportRunStatus = Literal["pending", "running", "cancelled", "completed"]
MarketSourceImportRunEventType = Literal["created", "started", "cancelled", "completed"]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class MarketSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_name: str
    source_type: MarketSourceType
    enabled: bool
    import_priority: int
    supports_raw: bool
    supports_graded: bool
    supports_variants: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class MarketSourceSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_source_id: int
    snapshot_date: date
    import_status: str
    total_records: int
    imported_records: int
    failed_records: int
    skipped_records: int
    source_metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class MarketSourceImportRunEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_run_id: int
    event_type: MarketSourceImportRunEventType
    previous_status: MarketSourceImportRunStatus | None = None
    new_status: MarketSourceImportRunStatus
    actor_user_id: int | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MarketSourceImportRunSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_source_id: int
    source_name: str
    source_type: MarketSourceType
    created_by_user_id: int | None = None
    status: MarketSourceImportRunStatus
    total_records: int = 0
    imported_records: int = 0
    failed_records: int = 0
    skipped_records: int = 0
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class MarketSourceImportRunRead(MarketSourceImportRunSummaryRead):
    events: list[MarketSourceImportRunEventRead] = Field(default_factory=list)


class MarketSourceImportRunListResponse(BaseModel):
    items: list[MarketSourceImportRunSummaryRead] = Field(default_factory=list)


class MarketSourceImportRunCreatePayload(BaseModel):
    market_source_id: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=8000)


class MarketSaleRecordImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_sale_record_id: int
    image_url: str | None = None
    image_sha256: str | None = None
    display_order: int
    created_at: datetime


class MarketSaleNormalizationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_sale_record_id: int
    issue_type: MarketSaleIssueType
    severity: MarketSaleIssueSeverity
    details_json: dict[str, Any]
    created_at: datetime


class MarketSaleReviewActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_sale_record_id: int
    action_type: MarketSaleReviewActionType
    actor_user_id: int | None = None
    details_json: dict[str, Any] = Field(default_factory=dict)
    before_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    after_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MarketSaleSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    market_source_id: int
    source_name: str
    source_type: MarketSourceType
    source_listing_id: str | None = None
    source_snapshot_id: int | None = None
    listing_type: MarketSaleListingType
    raw_title: str
    normalized_title: str | None = None
    raw_issue: str
    normalized_issue: str | None = None
    sale_price: Decimal | None = None
    shipping_price: Decimal | None = None
    total_price: Decimal | None = None
    currency_code: str
    sale_date: date | None = None
    is_graded: bool
    grading_company: MarketSaleGradingCompany | None = None
    is_signed: bool
    normalization_status: MarketSaleNormalizationStatus
    normalization_issue_count: int = 0
    created_at: datetime
    updated_at: datetime


class MarketSaleRead(MarketSaleSummaryRead):
    raw_publisher: str | None = None
    normalized_publisher: str | None = None
    raw_variant: str | None = None
    normalized_variant: str | None = None
    raw_grade: str | None = None
    normalized_grade: str | None = None
    raw_cert_number: str | None = None
    normalized_cert_number: str | None = None
    seller_name: str | None = None
    buyer_name: str | None = None
    source_url: str | None = None
    source_metadata_json: dict[str, Any]
    images: list[MarketSaleRecordImageRead] = Field(default_factory=list)
    normalization_issues: list[MarketSaleNormalizationIssueRead] = Field(default_factory=list)
    review_status: MarketSaleReviewStatus = "pending"
    review_actions: list[MarketSaleReviewActionRead] = Field(default_factory=list)
    source_snapshot: MarketSourceSnapshotRead | None = None


class MarketSaleReviewQueueItemRead(MarketSaleSummaryRead):
    review_status: MarketSaleReviewStatus = "pending"
    queue_classification: MarketSaleReviewClassification
    queue_priority: MarketSaleReviewPriority
    queue_reasons: list[str] = Field(default_factory=list)
    issue_types: list[MarketSaleIssueType] = Field(default_factory=list)


class MarketSaleReviewQueueResponse(BaseModel):
    items: list[MarketSaleReviewQueueItemRead] = Field(default_factory=list)
    total: int = 0


class MarketSaleReviewQueueSummaryRead(BaseModel):
    total: int = 0
    by_classification: dict[MarketSaleReviewClassification, int] = Field(default_factory=dict)
    by_priority: dict[MarketSaleReviewPriority, int] = Field(default_factory=dict)


class MarketSaleNormalizationUpdatePayload(BaseModel):
    normalized_title: str | None = Field(default=None, max_length=510)
    normalized_issue: str | None = Field(default=None, max_length=120)
    normalized_publisher: str | None = Field(default=None, max_length=255)
    normalized_variant: str | None = Field(default=None, max_length=255)
    normalized_grade: str | None = Field(default=None, max_length=120)
    normalized_cert_number: str | None = Field(default=None, max_length=120)
    normalization_status: MarketSaleNormalizationStatus | None = None
    mark_reviewed: bool = False
    review_note: str | None = Field(default=None, max_length=4096)

    _trim_normalized_title = field_validator("normalized_title", mode="before")(_trim)
    _trim_normalized_issue = field_validator("normalized_issue", mode="before")(_trim)
    _trim_normalized_publisher = field_validator("normalized_publisher", mode="before")(_trim)
    _trim_normalized_variant = field_validator("normalized_variant", mode="before")(_trim)
    _trim_normalized_grade = field_validator("normalized_grade", mode="before")(_trim)
    _trim_normalized_cert_number = field_validator("normalized_cert_number", mode="before")(_trim)
    _trim_review_note = field_validator("review_note", mode="before")(_trim)


class MarketSaleReviewActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=4096)

    _trim_reason = field_validator("reason", mode="before")(_trim)


class MarketSaleRecordImageUpsertPayload(BaseModel):
    image_url: str | None = None
    image_sha256: str | None = None
    display_order: int | None = None

    _trim_image_url = field_validator("image_url", mode="before")(_trim)
    _trim_image_sha256 = field_validator("image_sha256", mode="before")(_trim)


class MarketSaleUpsertPayload(BaseModel):
    market_source_id: int
    source_listing_id: str | None = None
    source_snapshot_id: int | None = None
    listing_type: MarketSaleListingType
    raw_title: str = Field(min_length=1, max_length=510)
    raw_issue: str = Field(min_length=1, max_length=120)
    raw_publisher: str | None = Field(default=None, max_length=255)
    raw_variant: str | None = Field(default=None, max_length=255)
    raw_grade: str | None = Field(default=None, max_length=120)
    raw_cert_number: str | None = Field(default=None, max_length=120)
    sale_price: Decimal | None = None
    shipping_price: Decimal | None = None
    total_price: Decimal | None = None
    currency_code: str = Field(min_length=1, max_length=8)
    sale_date: date | None = None
    seller_name: str | None = Field(default=None, max_length=255)
    buyer_name: str | None = Field(default=None, max_length=255)
    is_graded: bool = False
    grading_company: MarketSaleGradingCompany | None = None
    is_signed: bool = False
    source_url: str | None = Field(default=None, max_length=1024)
    source_metadata_json: dict[str, Any] = Field(default_factory=dict)
    images: list[MarketSaleRecordImageUpsertPayload] = Field(default_factory=list)

    _trim_source_listing_id = field_validator("source_listing_id", mode="before")(_trim)
    _trim_raw_title = field_validator("raw_title", mode="before")(_trim)
    _trim_raw_issue = field_validator("raw_issue", mode="before")(_trim)
    _trim_raw_publisher = field_validator("raw_publisher", mode="before")(_trim)
    _trim_raw_variant = field_validator("raw_variant", mode="before")(_trim)
    _trim_raw_grade = field_validator("raw_grade", mode="before")(_trim)
    _trim_raw_cert_number = field_validator("raw_cert_number", mode="before")(_trim)
    _trim_currency_code = field_validator("currency_code", mode="before")(_trim)
    _trim_seller_name = field_validator("seller_name", mode="before")(_trim)
    _trim_buyer_name = field_validator("buyer_name", mode="before")(_trim)
    _trim_source_url = field_validator("source_url", mode="before")(_trim)


class MarketSaleListResponse(BaseModel):
    items: list[MarketSaleSummaryRead] = Field(default_factory=list)

