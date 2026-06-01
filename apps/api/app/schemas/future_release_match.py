from __future__ import annotations

from pydantic import BaseModel, Field


class FutureReleaseMatchRead(BaseModel):
    id: int
    owner_id: int
    series_name: str
    issue_number: str
    publisher: str
    foc_date: str | None = None
    release_date: str | None = None
    release_id: int
    variant_count: int = Field(default=0, ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: str


class FutureReleaseMatchListRead(BaseModel):
    items: list[FutureReleaseMatchRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)
