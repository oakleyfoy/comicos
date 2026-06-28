"""P108 collection API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CollectionStats(BaseModel):
    books: int = 0
    orders: int = 0
    scans: int = 0
    retailer_imports: int = 0


class CollectionRead(BaseModel):
    id: int
    name: str
    collection_type: str
    is_default: bool
    source_collection_id: int | None = None
    source_snapshot_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    stats: CollectionStats = Field(default_factory=CollectionStats)


class CollectionListResponse(BaseModel):
    active_collection_id: int | None
    items: list[CollectionRead]


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    collection_type: str = "test"


class CollectionCloneRequest(BaseModel):
    name: str | None = None
    collection_type: str = "test"


class CollectionActiveRequest(BaseModel):
    collection_id: int


class CollectionResetRequest(BaseModel):
    admin_override: bool = False
