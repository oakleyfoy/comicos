from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MetadataAliasType = Literal["publisher", "series", "creator"]


def _validate_required_text(value: str, field_name: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} is required")
    return trimmed


class MetadataAliasCreate(BaseModel):
    alias_value: str = Field(min_length=1, max_length=255)
    canonical_value: str = Field(min_length=1, max_length=255)
    alias_type: MetadataAliasType = "publisher"

    @field_validator("alias_value", "canonical_value")
    @classmethod
    def validate_required_text(cls, value: str, info) -> str:
        return _validate_required_text(value, info.field_name)


class MetadataAliasUpdate(BaseModel):
    alias_value: str | None = Field(default=None, max_length=255)
    canonical_value: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("alias_value", "canonical_value")
    @classmethod
    def validate_optional_required_text(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _validate_required_text(value, info.field_name)


class MetadataAliasRead(BaseModel):
    id: int
    alias_value: str
    canonical_value: str
    alias_type: MetadataAliasType
    source: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
