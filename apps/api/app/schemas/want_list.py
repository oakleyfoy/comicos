from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

WantListPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
WantListItemStatus = Literal["WANTED", "FOUND", "ACQUIRED", "REMOVED"]


class WantListItemRead(BaseModel):
    id: int
    want_list_id: int
    owner_id: int
    publisher: str
    series_name: str
    issue_number: str
    variant_description: str
    priority: WantListPriority
    status: WantListItemStatus
    notes: str
    created_at: str
    updated_at: str


class WantListItemCreate(BaseModel):
    publisher: str = ""
    series_name: str = Field(min_length=1, max_length=200)
    issue_number: str = Field(min_length=1, max_length=32)
    variant_description: str = ""
    priority: WantListPriority = "MEDIUM"
    status: WantListItemStatus = "WANTED"
    notes: str = ""


class WantListItemUpdate(BaseModel):
    publisher: str | None = None
    series_name: str | None = Field(default=None, min_length=1, max_length=200)
    issue_number: str | None = Field(default=None, min_length=1, max_length=32)
    variant_description: str | None = None
    priority: WantListPriority | None = None
    status: WantListItemStatus | None = None
    notes: str | None = None


class WantListRead(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str
    is_active: bool
    created_at: str
    updated_at: str
    items: list[WantListItemRead] = Field(default_factory=list)


class WantListSummaryRead(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str
    is_active: bool
    item_count: int
    created_at: str
    updated_at: str


class WantListListRead(BaseModel):
    items: list[WantListSummaryRead]


class WantListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    is_active: bool = True


class WantListUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    is_active: bool | None = None


class WantListItemDeleteResponse(BaseModel):
    deleted: bool
    id: int
