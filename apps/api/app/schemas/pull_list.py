from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PullListStatus = Literal["ACTIVE", "PAUSED", "COMPLETED", "DROPPED"]
PullListIssueActionState = Literal["UPCOMING", "FOC_APPROACHING", "RELEASED", "MISSED"]


class PullListCreate(BaseModel):
    publisher: str = Field(min_length=1, max_length=120)
    series_name: str = Field(min_length=1, max_length=200)
    canonical_series_id: int | None = None
    status: PullListStatus = "ACTIVE"


class PullListUpdate(BaseModel):
    publisher: str | None = Field(default=None, min_length=1, max_length=120)
    series_name: str | None = Field(default=None, min_length=1, max_length=200)
    canonical_series_id: int | None = None
    status: PullListStatus | None = None


class PullListIssueAttachRequest(BaseModel):
    release_id: int = Field(ge=1)


class PullListIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pull_list_id: int
    release_id: int
    issue_number: str
    title: str
    release_date: date | None
    foc_date: date | None
    action_state: PullListIssueActionState
    created_at: datetime
    updated_at: datetime


class PullListRead(BaseModel):
    id: int
    owner_id: int
    publisher: str
    series_name: str
    canonical_series_id: int | None
    status: PullListStatus
    upcoming_issue_count: int = 0
    created_at: datetime
    updated_at: datetime


class PullListDetailRead(BaseModel):
    pull_list: PullListRead
    issues: list[PullListIssueRead]


class PullListListResponse(BaseModel):
    items: list[PullListRead]
    total_items: int
    limit: int
    offset: int
