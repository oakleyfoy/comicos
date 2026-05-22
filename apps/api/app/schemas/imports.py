from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.ai import ParseOrderResponse

DraftImportStatus = Literal["draft", "confirmed", "discarded"]
DraftImportSortBy = Literal["created_at", "updated_at", "confidence_score", "status"]


def validate_raw_text(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("raw_text is required")
    return trimmed


class DraftImportCreate(BaseModel):
    raw_text: str = Field(min_length=1)

    @field_validator("raw_text")
    @classmethod
    def validate_create_raw_text(cls, value: str) -> str:
        return validate_raw_text(value)


class ManualDraftImportCreate(ParseOrderResponse):
    raw_text: str | None = None
    source_type: Literal["manual_draft"] = "manual_draft"
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("raw_text")
    @classmethod
    def validate_manual_raw_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class DraftImportUpdate(BaseModel):
    raw_text: str | None = None
    parsed_payload_json: ParseOrderResponse | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("raw_text")
    @classmethod
    def validate_update_raw_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_raw_text(value)


class DraftImportRead(BaseModel):
    id: int
    raw_text: str
    parsed_payload_json: ParseOrderResponse
    confidence_score: Decimal
    status: DraftImportStatus
    order_id: int | None = None
    created_at: datetime
    updated_at: datetime


class DraftImportListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[DraftImportRead]


class DraftImportConfirmResponse(BaseModel):
    import_id: int
    status: DraftImportStatus
    order_id: int
    total_items: int
    total_copies_created: int
    all_in_total: Decimal
