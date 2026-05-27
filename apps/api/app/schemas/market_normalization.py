from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MarketNormalizationRunStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]
MarketNormalizationStatus = Literal["SUCCESS", "PARTIAL", "FAILED"]
MarketNormalizationConditionBand = Literal["UNKNOWN", "POOR", "GOOD", "VERY_GOOD", "FINE", "VF", "NM"]
MarketNormalizationIssueType = Literal[
    "MISSING_FIELD",
    "AMBIGUOUS_MATCH",
    "INVALID_PRICE",
    "CONDITION_PARSE_ERROR",
    "VARIANT_CONFLICT",
]
MarketNormalizationIssueSeverity = Literal["LOW", "MEDIUM", "HIGH"]
MarketNormalizationEventType = Literal[
    "RUN_STARTED",
    "RECORD_NORMALIZED",
    "RECORD_PARTIAL",
    "RECORD_FAILED",
    "RUN_COMPLETED",
]


class MarketNormalizationRunCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_batch_id: int = Field(ge=1)


class MarketNormalizationRunSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestion_batch_id: int
    owner_user_id: int | None = None
    run_status: MarketNormalizationRunStatus | str
    total_records: int
    successful_records: int
    partial_records: int
    failed_records: int
    run_checksum: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class MarketNormalizationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    normalization_run_id: int
    event_type: MarketNormalizationEventType | str
    metadata_json: dict[str, Any]
    created_at: datetime


class MarketNormalizationRunDetailRead(MarketNormalizationRunSummaryRead):
    events: list[MarketNormalizationEventRead] = Field(default_factory=list)


class MarketAcquisitionNormalizedCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestion_candidate_id: int
    normalization_run_id: int
    owner_user_id: int | None = None
    canonical_title: str
    canonical_publisher: str | None = None
    canonical_issue_number: str | None = None
    canonical_variant: str | None = None
    normalized_condition_band: MarketNormalizationConditionBand | str
    normalized_price: Decimal | None = None
    normalized_currency: str | None = None
    normalized_fmv_estimate: Decimal | None = None
    normalized_liquidity_hint: str | None = None
    normalized_grade_potential: str | None = None
    canonical_key: str
    normalization_flags_json: dict[str, Any] | None = None
    normalization_status: MarketNormalizationStatus | str
    created_at: datetime
    updated_at: datetime


class MarketNormalizationIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    normalization_run_id: int
    ingestion_candidate_id: int
    issue_type: MarketNormalizationIssueType | str
    severity: MarketNormalizationIssueSeverity | str
    issue_detail_json: dict[str, Any] | None = None
    created_at: datetime


class MarketNormalizationHealthRead(BaseModel):
    candidate_status_counts: dict[str, int] = Field(default_factory=dict)
    issue_type_counts: dict[str, int] = Field(default_factory=dict)
    normalization_flag_counts: dict[str, int] = Field(default_factory=dict)
    canonical_full_success_rate_pct: Decimal | None = None
    last_normalization_completed_at: datetime | None = None


class MarketNormalizationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketNormalizationRunSummaryRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    health: MarketNormalizationHealthRead = Field(default_factory=MarketNormalizationHealthRead)


class MarketAcquisitionNormalizedCandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketAcquisitionNormalizedCandidateRead]
    total_items: int
    limit: int
    offset: int


class MarketNormalizationIssueListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarketNormalizationIssueRead]
    total_items: int
    limit: int
    offset: int
