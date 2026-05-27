from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ScanIngestionSourceType = Literal["EPSON", "FUJITSU", "MOBILE", "ZIP_IMPORT", "MANUAL_UPLOAD"]
ScanUploadSourceType = Literal["drag_drop", "zip_upload", "scanner_batch", "manual_upload"]
ScanIngestionBatchStatus = Literal["PENDING", "PROCESSING", "COMPLETE", "FAILED"]
ScanImageProcessingStatus = Literal["INGESTED", "NORMALIZED", "FAILED"]
ScanVariantType = Literal["normalized_image", "thumbnail", "rotated_image", "crop_preview"]
ScanIngestionEventType = Literal[
    "UPLOAD_SESSION_STARTED",
    "BATCH_CREATED",
    "IMAGE_REGISTERED",
    "DUPLICATE_DETECTED",
    "IMAGE_FAILED",
    "VARIANT_CREATED",
    "BATCH_COMPLETED",
]


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class ScanBatchUploadPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: ScanIngestionSourceType
    upload_source: ScanUploadSourceType
    scanner_make: str | None = Field(default=None, max_length=120)
    scanner_model: str | None = Field(default=None, max_length=120)
    scanner_profile: str | None = Field(default=None, max_length=200)
    color_mode: str | None = Field(default=None, max_length=40)
    normalized_dpi: int = Field(default=300, ge=72, le=2400)
    create_thumbnail: bool = True
    create_normalized_variant: bool = True

    _trim_scanner_make = field_validator("scanner_make", mode="before")(_trim)
    _trim_scanner_model = field_validator("scanner_model", mode="before")(_trim)
    _trim_scanner_profile = field_validator("scanner_profile", mode="before")(_trim)
    _trim_color_mode = field_validator("color_mode", mode="before")(_trim)


class RegisteredScanFilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_filename: str = Field(min_length=1, max_length=512)
    storage_path: str = Field(min_length=1, max_length=1024)
    mime_type: str = Field(min_length=1, max_length=128)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    dpi_x: int | None = Field(default=None, ge=1)
    dpi_y: int | None = Field(default=None, ge=1)
    file_size_bytes: int = Field(ge=1)
    sha256_checksum: str = Field(min_length=64, max_length=64)
    scanner_make: str | None = Field(default=None, max_length=120)
    scanner_model: str | None = Field(default=None, max_length=120)
    scanner_profile: str | None = Field(default=None, max_length=200)
    color_mode: str | None = Field(default=None, max_length=40)

    _trim_scanner_make = field_validator("scanner_make", mode="before")(_trim)
    _trim_scanner_model = field_validator("scanner_model", mode="before")(_trim)
    _trim_scanner_profile = field_validator("scanner_profile", mode="before")(_trim)
    _trim_color_mode = field_validator("color_mode", mode="before")(_trim)


class ScanBatchCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: ScanIngestionSourceType
    upload_source: ScanUploadSourceType
    normalized_dpi: int = Field(default=300, ge=72, le=2400)
    files: list[RegisteredScanFilePayload] = Field(min_length=1)


class ScanImageVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_scan_image_id: int
    variant_type: ScanVariantType | str
    storage_backend: str
    storage_path: str
    width: int | None = None
    height: int | None = None
    checksum: str
    created_at: datetime


class ScanImageSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ingestion_batch_id: int
    sequence_index: int
    original_filename: str
    storage_backend: str
    storage_path: str
    mime_type: str
    width: int | None = None
    height: int | None = None
    dpi_x: int | None = None
    dpi_y: int | None = None
    normalized_dpi_x: int | None = None
    normalized_dpi_y: int | None = None
    file_size_bytes: int
    sha256_checksum: str
    scanner_make: str | None = None
    scanner_model: str | None = None
    scanner_profile: str | None = None
    color_mode: str | None = None
    processing_status: ScanImageProcessingStatus | str
    is_duplicate: bool
    duplicate_of_scan_image_id: int | None = None
    failure_reason: str | None = None
    created_at: datetime


class ScanImageRead(ScanImageSummaryRead):
    variants: list[ScanImageVariantRead] = Field(default_factory=list)


class ScanIngestionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestion_batch_id: int
    scan_image_id: int | None = None
    event_type: ScanIngestionEventType | str
    metadata_json: dict
    created_at: datetime


class ScanUploadSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    upload_source: ScanUploadSourceType | str
    session_checksum: str
    total_files: int
    successful_files: int
    failed_files: int
    duplicate_files: int
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime


class ScanIngestionBatchSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    upload_session_id: int
    source_type: ScanIngestionSourceType | str
    batch_status: ScanIngestionBatchStatus | str
    image_count: int
    failed_count: int
    duplicate_count: int
    ingestion_checksum: str
    created_at: datetime
    completed_at: datetime | None = None


class ScanIngestionBatchRead(ScanIngestionBatchSummaryRead):
    upload_session: ScanUploadSessionRead
    images: list[ScanImageSummaryRead] = Field(default_factory=list)
    events: list[ScanIngestionEventRead] = Field(default_factory=list)


class ScanIngestionBatchListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanIngestionBatchSummaryRead]
    total_items: int
    limit: int
    offset: int
    source_type_counts: dict[str, int] = Field(default_factory=dict)
    duplicate_image_count: int = 0
    failed_image_count: int = 0


class ScanImageListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanImageSummaryRead]
    total_items: int
    limit: int
    offset: int

