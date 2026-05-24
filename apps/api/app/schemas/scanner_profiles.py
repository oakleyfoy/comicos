"""Scanner preset metadata (persisted facts only — no drivers or transforms)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ScannerTypeLiteral = Literal["fujitsu_bulk", "epson_high_res", "generic_flatbed", "manual_upload"]
ColorModeLiteral = Literal["color", "grayscale", "black_and_white"]
FileFormatLiteral = Literal["png", "jpg", "tif"]
RecommendedUseLiteral = Literal[
    "bulk_ingest",
    "high_res_review",
    "intake_receiving",
    "archival_scan",
]


class ScannerProfileSnapshotRead(BaseModel):
    """Immutable capture configuration persisted on scan-session creation."""

    profile_name: str
    scanner_type: ScannerTypeLiteral
    dpi: int | None = None
    color_mode: ColorModeLiteral
    file_format: FileFormatLiteral
    duplex_enabled: bool = False
    feeder_enabled: bool = False
    recommended_use: RecommendedUseLiteral


class ScannerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int | None
    profile_name: str
    scanner_type: ScannerTypeLiteral
    dpi: int | None = None
    color_mode: ColorModeLiteral
    file_format: FileFormatLiteral
    duplex_enabled: bool
    feeder_enabled: bool
    recommended_use: RecommendedUseLiteral
    is_default: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ScannerProfileCreatePayload(BaseModel):
    profile_name: str = Field(min_length=1, max_length=200)
    scanner_type: ScannerTypeLiteral
    dpi: int | None = Field(default=None, ge=72, le=9600)
    color_mode: ColorModeLiteral = "color"
    file_format: FileFormatLiteral = "png"
    duplex_enabled: bool = False
    feeder_enabled: bool = False
    recommended_use: RecommendedUseLiteral = "bulk_ingest"
    is_default: bool = False
    notes: str | None = Field(default=None, max_length=8000)


class ScannerProfileUpdatePayload(BaseModel):
    profile_name: str | None = Field(default=None, min_length=1, max_length=200)
    scanner_type: ScannerTypeLiteral | None = None
    dpi: int | None = Field(default=None, ge=72, le=9600)
    color_mode: ColorModeLiteral | None = None
    file_format: FileFormatLiteral | None = None
    duplex_enabled: bool | None = None
    feeder_enabled: bool | None = None
    recommended_use: RecommendedUseLiteral | None = None
    is_default: bool | None = None
    notes: str | None = Field(default=None, max_length=8000)


class ScannerProfileListResponse(BaseModel):
    items: list[ScannerProfileRead] = Field(default_factory=list)

