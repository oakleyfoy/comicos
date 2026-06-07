from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MarketAcquisitionExternalSourceType = Literal[
    "manual_input",
    "csv_import",
    "api_feed",
    "auction_snapshot",
    "curated_feed",
]
MarketAcquisitionIngestionStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
MarketAcquisitionRawProcessingStatus = Literal["PENDING", "NORMALIZED", "FAILED"]
MarketAcquisitionIngestionEventType = Literal[
    "BATCH_CREATED",
    "RECORD_PARSED",
    "RECORD_NORMALIZED",
    "RECORD_REJECTED",
    "BATCH_COMPLETED",
]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class MarketAcquisitionIngestionBatchCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_source_type: MarketAcquisitionExternalSourceType
    batch_file_name: str | None = Field(default=None, max_length=512)
    records: list[dict[str, Any]] = Field(min_length=1)

    _trim_batch_file_name = field_validator("batch_file_name", mode="before")(_trim)


class MarketAcquisitionCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    external_source_type: MarketAcquisitionExternalSourceType | str
    external_listing_id: str | None = None
    source_name: str | None = None
    title: str
    publisher: str | None = None
    issue_number: str | None = None
    variant: str | None = None
    condition_raw: str | None = None
    asking_price: Decimal | None = None
    currency: str | None = None
    external_fmv_estimate: Decimal | None = None
    raw_payload_json: dict[str, Any] | None = None
    ingestion_batch_id: int
    normalized_flag: bool
    created_at: datetime
    updated_at: datetime


class MarketAcquisitionRawSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestion_batch_id: int
    raw_record_json: dict[str, Any]
    raw_hash: str
    processing_status: MarketAcquisitionRawProcessingStatus | str
    error_message: str | None = None
    created_at: datetime


class MarketAcquisitionIngestionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestion_batch_id: int
    event_type: MarketAcquisitionIngestionEventType | str
    metadata_json: dict[str, Any]
    created_at: datetime


class MarketAcquisitionIngestionBatchSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None = None
    batch_source_type: MarketAcquisitionExternalSourceType | str
    batch_file_name: str | None = None
    batch_checksum: str
    total_records: int
    successful_records: int
    failed_records: int
    ingestion_status: MarketAcquisitionIngestionStatus | str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class MarketAcquisitionIngestionBatchRead(MarketAcquisitionIngestionBatchSummaryRead):
    events: list[MarketAcquisitionIngestionEventRead] = Field(default_factory=list)


class MarketAcquisitionIngestionBatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "OK"
    message: str = ""
    items: list[MarketAcquisitionIngestionBatchSummaryRead]
    total_items: int
    limit: int
    offset: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    last_ingestion_at: datetime | None = None


class MarketAcquisitionRawSourceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "OK"
    message: str = ""
    items: list[MarketAcquisitionRawSourceRead]
    total_items: int
    limit: int
    offset: int
