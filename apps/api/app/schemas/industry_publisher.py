from __future__ import annotations

from pydantic import BaseModel, Field


class IndustryPublisherRead(BaseModel):
    id: int
    owner_id: int
    publisher_code: str
    publisher_name: str
    scan_enabled: bool
    inclusion_status: str
    scan_priority: int
    classification_mode: str
    created_at: str
    updated_at: str


class IndustryPublisherListRead(BaseModel):
    items: list[IndustryPublisherRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)


class IndustryPublisherUpdate(BaseModel):
    scan_enabled: bool | None = None
    inclusion_status: str | None = None
    scan_priority: int | None = Field(default=None, ge=1, le=1000)
    classification_mode: str | None = None
